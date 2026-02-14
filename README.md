# Secure Cloud Run Function with Cloud Scheduler

A complete guide for deploying internal-only Cloud Run functions on Google Cloud Platform with automated scheduling and optional Apps Script integration.

## Overview

This repository demonstrates how to:
- Deploy a secure, internal-only Cloud Run function (Gen 2)
- Automate execution with Cloud Scheduler
- Grant Google Drive/Workspace API access
- Trigger functions on-demand from Google Apps Script

## Prerequisites

- Google Cloud Project with billing enabled
- `gcloud` CLI installed and configured
- Basic familiarity with Python and Google Cloud Platform

## Project Structure

```
.
├── main.py              # Your Python function code
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## Step 1: Prepare Your Code

### 1.1 Create `requirements.txt`

Define your Python dependencies:

```plaintext
functions-framework==3.*
google-api-python-client==2.*
google-auth==2.*
```

### 1.2 Create `main.py`

Your function must include the `@functions_framework.http` decorator:

```python
import os
import functions_framework
import google.auth
from googleapiclient.discovery import build

@functions_framework.http
def main(request):
    """
    HTTP Cloud Function entry point.
    Args:
        request (flask.Request): The request object.
    Returns:
        The response text, or any set of values that can be turned into a
        Response object using `make_response`.
    """
    try:
        # Get default credentials
        creds, project_id = google.auth.default()
        
        # Your business logic here
        # Example: Interact with Google Drive API
        # service = build('drive', 'v3', credentials=creds)
        
        return {"status": "success", "message": "Function executed successfully"}, 200
        
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500
```

## Step 2: Deploy the Function

Deploy as a Gen 2 Cloud Function with internal-only access:

```bash
gcloud functions deploy your-function-name \
  --gen2 \
  --runtime=python310 \
  --region=europe-west1 \
  --source=. \
  --entry-point=main \
  --trigger-http \
  --ingress-settings=internal-only
```

**Key Parameters:**
- `--gen2`: Uses Cloud Run (Gen 2) infrastructure
- `--ingress-settings=internal-only`: Blocks all public internet traffic
- `--entry-point=main`: Points to the function name in your code

## Step 3: Create Service Account for Authentication

Since the function is internal-only, you need a service account to invoke it.

### 3.1 Create the Service Account

```bash
gcloud iam service-accounts create function-scheduler-sa \
    --display-name="Function Scheduler Service Account"
```

### 3.2 Grant Invocation Permission

```bash
gcloud run services add-iam-policy-binding your-function-name \
    --region=europe-west1 \
    --member="serviceAccount:function-scheduler-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/run.invoker"
```

## Step 4: Configure Google Drive/Workspace Access (Optional)

If your function needs to access Google Drive or other Workspace APIs:

### 4.1 Identify the Runtime Service Account

```bash
gcloud run services describe your-function-name \
    --region=europe-west1 \
    --format="value(template.serviceAccount)"
```

### 4.2 Share Drive Resources

Copy the service account email and share your Drive folder/Shared Drive with it, granting appropriate permissions (e.g., Content Manager, Editor).

## Step 5: Automate with Cloud Scheduler

Set up automatic execution using Cloud Scheduler:

```bash
gcloud scheduler jobs create http scheduled-function-job \
    --location=europe-west1 \
    --schedule="0 9 * * 1-5" \
    --time-zone="Europe/Berlin" \
    --uri="https://YOUR-CLOUD-RUN-URL.run.app/" \
    --http-method=GET \
    --oidc-service-account-email="function-scheduler-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com"
```

**Common Cron Schedules:**
- `0 9 * * 1-5`: Every weekday at 9 AM
- `0 */6 * * *`: Every 6 hours
- `*/30 * * * *`: Every 30 minutes
- `0 0 * * 0`: Every Sunday at midnight

### 5.1 Test the Scheduled Job

```bash
gcloud scheduler jobs run scheduled-function-job --location=europe-west1
```

## Step 6: Trigger from Google Apps Script (Optional)

To invoke your internal function from a Google Sheet or Apps Script:

### 6.1 Configure Apps Script Manifest

Enable "Show manifest file" in Apps Script settings, then edit `appsscript.json`:

```json
{
  "oauthScopes": [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/script.external_request"
  ]
}
```

### 6.2 Create Trigger Function

```javascript
function triggerCloudFunction() {
  const projectId = 'YOUR_PROJECT_ID';
  const location = 'europe-west1';
  const jobId = 'scheduled-function-job';
  
  const url = `https://cloudscheduler.googleapis.com/v1/projects/${projectId}/locations/${location}/jobs/${jobId}:run`;
  
  const options = {
    method: 'post',
    headers: {
      Authorization: 'Bearer ' + ScriptApp.getOAuthToken() 
    },
    muteHttpExceptions: true
  };
  
  const response = UrlFetchApp.fetch(url, options);
  Logger.log(response.getContentText());
  
  return JSON.parse(response.getContentText());
}
```

## Updating Your Function

To update an existing deployment:

### Option 1: Organize in Project Folder

```bash
# Create project directory
mkdir my-cloud-function

# Move files
mv main.py requirements.txt my-cloud-function/

# Navigate to directory
cd my-cloud-function

# Redeploy (uses same function name)
gcloud functions deploy your-function-name \
  --gen2 \
  --runtime=python310 \
  --region=europe-west1 \
  --source=. \
  --entry-point=main \
  --trigger-http \
  --ingress-settings=internal-only
```

### Option 2: Deploy from Root

```bash
# Update code in place and redeploy
gcloud functions deploy your-function-name \
  --gen2 \
  --runtime=python310 \
  --region=europe-west1 \
  --source=. \
  --entry-point=main \
  --trigger-http \
  --ingress-settings=internal-only
```

**Note:** Updates deploy with zero downtime. The old version continues serving requests while the new version builds.

## Monitoring and Logs

### View Function Logs

```bash
gcloud functions logs read your-function-name \
    --region=europe-west1 \
    --limit=50
```

### View Scheduler Job Logs

```bash
gcloud scheduler jobs describe scheduled-function-job \
    --location=europe-west1
```

### Cloud Console

Visit the [Cloud Functions Console](https://console.cloud.google.com/functions) for:
- Execution metrics and graphs
- Real-time logs
- Error tracking
- Invocation history

## Security Best Practices

1. **Never expose internal functions publicly** - Always use `--ingress-settings=internal-only`
2. **Use service accounts** - Create dedicated service accounts for each function/purpose
3. **Principle of least privilege** - Grant only necessary IAM roles
4. **Rotate credentials** - Regularly review and update service account permissions
5. **Enable Cloud Audit Logs** - Track who accesses your functions

## Troubleshooting

### Function Not Triggering

- Verify service account has `roles/run.invoker` permission
- Check Cloud Scheduler job is enabled: `gcloud scheduler jobs describe JOB_NAME --location=LOCATION`
- Review Cloud Scheduler logs for authentication errors

### Permission Denied Errors

- Confirm the runtime service account has access to required resources (Drive, etc.)
- Verify API services are enabled: `gcloud services list --enabled`

### Function Times Out

- Increase timeout: Add `--timeout=540s` to deployment command (max 540s for Gen 2)
- Optimize your code for faster execution
- Consider using Cloud Tasks for longer-running jobs

## Cost Considerations

- **Cloud Functions:** Free tier includes 2M invocations/month
- **Cloud Scheduler:** First 3 jobs per month are free
- **Cloud Run (Gen 2 backend):** Pay only for execution time
- See [Google Cloud Pricing Calculator](https://cloud.google.com/products/calculator) for estimates

## Additional Resources

- [Cloud Functions Documentation](https://cloud.google.com/functions/docs)
- [Cloud Scheduler Documentation](https://cloud.google.com/scheduler/docs)
- [Service Account Best Practices](https://cloud.google.com/iam/docs/best-practices-service-accounts)
- [Cron Schedule Format](https://cloud.google.com/scheduler/docs/configuring/cron-job-schedules)

## License

MIT License - See LICENSE file for details

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.
