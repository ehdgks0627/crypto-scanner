# Deployment Automation

Production deployment currently uses an EC2 pull-based deployer. The EC2 instance polls `origin/main`, deploys new commits locally, and never accepts inbound deployment access from GitHub.

GitHub Actions OIDC + AWS Systems Manager remains documented as a future option. The workflow is intentionally `workflow_dispatch` only until the AWS IAM/OIDC and GitHub environment settings are completed.

## Active Flow

```
push to main
  -> EC2 deploy-watch loop polls origin/main
  -> new commit detected
  -> EC2 runs scripts/deploy-production.sh
  -> docker compose build / migrate / up
  -> HTTPS health check
```

## EC2 Pull Deployer

`scripts/deploy-watch.sh` is the long-running worker. It:

1. Polls `origin/main` every 60 seconds.
2. Compares the remote SHA with the currently checked out SHA.
3. Runs `scripts/deploy-production.sh` when a new commit appears.
4. Delays retries for the same failed SHA for 300 seconds.
5. Writes state and logs outside the repository under `~/.local/state/crypto-scanner-deploy`.

Start it in `tmux`:

```bash
tmux new-session -d -s crypto-scanner-deploy \
  'cd /opt/crypto-scanner && APP_DIR=/opt/crypto-scanner HEALTHCHECK_URL=https://pqc.sprout.kr/api/health/ POLL_SECONDS=60 bash scripts/deploy-watch.sh'
```

Inspect it:

```bash
tmux attach -t crypto-scanner-deploy
tail -f ~/.local/state/crypto-scanner-deploy/deploy-watch.log
```

Stop it:

```bash
tmux kill-session -t crypto-scanner-deploy
```

The app checkout at `/opt/crypto-scanner` must be treated as deployment-only. Keep runtime state in `.env`, Docker volumes, or external services.

## Future OIDC Flow

```
manual workflow dispatch
  -> GitHub Actions backend/frontend tests
  -> GitHub OIDC token
  -> AWS STS temporary role credentials
  -> SSM SendCommand
  -> EC2 runs scripts/deploy-production.sh
  -> docker compose build / migrate / up
  -> HTTPS health check
```

## GitHub OIDC Configuration

Create a GitHub environment named `production` and restrict deployments to `main`.

Repository or environment variables:

| Name | Example | Description |
|---|---|---|
| `AWS_REGION` | `ap-northeast-2` | AWS region for EC2 and SSM |
| `SSM_INSTANCE_ID` | `i-0123456789abcdef0` | EC2 instance managed by SSM |
| `APP_DIR` | `/opt/crypto-scanner` | Git checkout on the EC2 instance |
| `HEALTHCHECK_URL` | `https://pqc.sprout.kr/api/health/` | Post-deploy health check URL |
| `SSM_RUN_AS_USER` | `ubuntu` | Linux user that owns the app checkout |

Repository or environment secret:

| Name | Description |
|---|---|
| `AWS_DEPLOY_ROLE_ARN` | IAM role ARN assumed by GitHub Actions through OIDC |

## AWS OIDC Role

Create an IAM OIDC provider for `https://token.actions.githubusercontent.com` with audience `sts.amazonaws.com`.

Trust policy for the GitHub deploy role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::<account-id>:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
          "token.actions.githubusercontent.com:sub": "repo:ehdgks0627/crypto-scanner:environment:production"
        }
      }
    }
  ]
}
```

The `sub` condition intentionally binds deployment to the GitHub `production` environment. Configure that environment so only `main` can deploy.

Minimum permissions policy for the deploy role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "ssm:SendCommand",
      "Resource": [
        "arn:aws:ssm:<region>::document/AWS-RunShellScript",
        "arn:aws:ec2:<region>:<account-id>:instance/<instance-id>"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "ssm:GetCommandInvocation",
        "ssm:ListCommandInvocations"
      ],
      "Resource": "*"
    }
  ]
}
```

## EC2 Requirements

Attach an instance profile with `AmazonSSMManagedInstanceCore` to the EC2 instance. The instance must appear in AWS Systems Manager managed nodes before GitHub Actions can deploy to it.

The current Ubuntu snap service name is:

```bash
sudo systemctl status snap.amazon-ssm-agent.amazon-ssm-agent.service
```

The app checkout must exist at `APP_DIR`, be owned by `SSM_RUN_AS_USER`, and have `origin` pointed at this repository:

```bash
cd /opt/crypto-scanner
git remote -v
git status --short
```

The deployment script refuses to overwrite local changes unless the file contents already match the target commit. Treat `/opt/crypto-scanner` as a deployment-only checkout; keep runtime state in `.env`, Docker volumes, or external services.

The deployment user must be able to run Docker. On the current EC2 instance, `ubuntu` uses passwordless sudo for Docker, which the script detects automatically.

## Deployment Script Behavior

`scripts/deploy-production.sh`:

1. Fetches `origin/main`.
2. Verifies `DEPLOY_SHA` is reachable from `origin/main`.
3. Aborts on unsafe local worktree changes.
4. Checks out the exact commit in detached HEAD mode.
5. Runs `docker compose build`.
6. Runs Django migrations with `--entrypoint python`.
7. Starts services with `docker compose up -d --remove-orphans`.
8. Polls `HEALTHCHECK_URL`.

Manual dry run from EC2:

```bash
cd /opt/crypto-scanner
DEPLOY_SHA="$(git rev-parse origin/main)" \
HEALTHCHECK_URL="https://pqc.sprout.kr/api/health/" \
bash scripts/deploy-production.sh
```
