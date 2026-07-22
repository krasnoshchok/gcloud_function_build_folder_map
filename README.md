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
├── azure-pipelines.yml  # Azure DevOps CI/CD pipeline (see below)
└── README.md           # This file
```

## CI/CD Pipeline (Azure DevOps)

This repo includes `azure-pipelines.yml`, which automates everything in "Step 2: Deploy the Function" below. Every push to `main` validates and redeploys the function; every pull request into `main` is validated only (no deploy). Once it's set up, you no longer need to run `gcloud functions deploy` by hand.

### What it does

The pipeline has two stages:

1. **Validate** (runs on every PR and on `main`)
   - Installs `requirements.txt`
   - Byte-compiles `main.py` (`python -m py_compile`) to catch syntax errors before deploying

2. **Deploy** (runs only on pushes to `main`, after Validate passes)
   - Downloads the GCP service account key from Azure DevOps' Secure Files (never committed to the repo or written to logs)
   - Installs the `gcloud` CLI on the build agent
   - Authenticates with `gcloud auth activate-service-account`
   - Runs `gcloud functions deploy` as a **Gen2** function with `--ingress-settings=internal-only` and `--no-allow-unauthenticated`, matching the security posture described in this README
   - Passes `SHARED_DRIVE_FOLDER` and `SHARED_DRIVE_ID` via `--set-env-vars`, sourced live from an Azure DevOps variable group — so changing those values in Azure DevOps and re-running the pipeline is enough to update the deployed function's config
   - Revokes the service account credentials from the build agent at the end of the job, whether it succeeded or failed

### One-time setup in Azure DevOps

Before the pipeline can run, configure three things in your Azure DevOps project:

**1. Secure file — the deployment credential**

In *Pipelines → Library → Secure files*, upload your GCP service account key JSON, named exactly `gcp-sa-key.json`. Authorize it for use by this pipeline (or the `production` environment) under its permissions tab.

The service account behind this key needs, at minimum:
- `roles/run.developer` (or `roles/cloudfunctions.developer`)
- `roles/iam.serviceAccountUser`

on the target GCP project.

**2. Variable group — deployment configuration**

In *Pipelines → Library → Variable groups*, create a group named `gcp-folder-map-function` with these variables:

| Variable | Description | Example |
|---|---|---|
| `GCP_PROJECT_ID` | Target GCP project | `my-gcp-project` |
| `GCP_REGION` | Deployment region | `europe-west1` |
| `FUNCTION_NAME` | Cloud Function/Run service name | `folder-map-function` |
| `RUNTIME` | Python runtime for Gen2 | `python312` |
| `SHARED_DRIVE_FOLDER` | Folder ID the map file is uploaded to | `1AbCdEfGhIjKlMnOp` |
| `SHARED_DRIVE_ID` | Shared Drive ID to scan for folders | `0AbCdEfGhIjKlMnOp` |

None of these values are secret (the sensitive part is the key file above), so plain variables are fine.

**3. Environment — deployment history and gates**

In *Pipelines → Environments*, create an environment named `production`. The `Deploy` stage targets this environment, which gives you a deployment history in Azure DevOps and lets you optionally add a manual-approval check before deploys go out.

### Running it

Point an Azure DevOps pipeline at `azure-pipelines.yml` (*Pipelines → New pipeline → Existing YAML file*). From then on:

- Opening a PR into `main` triggers **Validate** only.
- Merging/pushing to `main` triggers **Validate** then **Deploy**.

To update the deployed environment variables without a code change, edit the variable group and re-run the pipeline — no local `gcloud` needed.

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
