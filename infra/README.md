# Wathiq on Azure

Everything needed to run Wathiq on AKS: the Bicep that creates the resources, the Helm chart
that deploys the workloads, and the scripts that tie them together.

> **This subscription contains a working system in `filingsiq-rg`. Wathiq never touches it.**
> The rule is enforced in three places rather than remembered:
>
> 1. `main.bicep` deploys at **resource-group scope**, so it physically cannot create, modify
>    or delete anything outside the group it is given.
> 2. `deploy.sh` and `teardown.sh` check the group name against an **exact-match allow-list**
>    (`rg-wathiq-dev`, `rg-wathiq-test`) and refuse anything else.
> 3. `teardown.sh` additionally requires the group to carry the tags `application=wathiq` and
>    `teardown=allowed` that Bicep stamps on it, and makes you type the name back.
>
> Wathiq also creates its **own copy of every service** rather than reusing an existing one —
> its own Key Vault, its own registry, its own Cognitive Services accounts. Nothing is shared,
> so nothing can be broken by sharing.

---

## What it costs

Verified against the Azure retail price API for `eastus2`, September 2026.

| # | Resource | SKU | USD/mo | Note |
|---|---|---|---|---|
| 1 | AKS control plane | Free tier | **0.00** | No SLA; fine for a demo |
| 2 | AKS node pool | 1 × `Standard_D2s_v3` | **70.08** | $0.096/hr, verified — see below |
| 3 | Node OS disk | 32 GB Premium SSD | ~5.00 | AKS minimum |
| 4 | PostgreSQL Flexible | `B1ms` + 32 GB | ~16.00 | Smallest burstable |
| 5 | Container Registry | Basic | **5.07** | $0.1666/day, verified |
| 6 | Storage (ADLS Gen2) | StorageV2 LRS Hot, HNS on | ~1.00 | A few GB of PDFs |
| 6b | Storage (Azure ML) | StorageV2 LRS Hot, HNS **off** | ~0.20 | ML refuses an HNS account |
| 7 | Key Vault | Standard | ~0.10 | Per-operation |
| 8 | Log Analytics + App Insights | Pay-per-GB | ~0.00 | 5 GB/mo free grant |
| 9 | Azure OpenAI | S0 pay-per-token | ~2.00 | Idle costs nothing |
| 10 | Document Intelligence | **F0 free** | **0.00** | 500 pages/mo |
| 11 | Content Safety | S0 | ~1.00 | F0 was taken |
| 12 | Azure ML | Workspace only (compute opt-in) | ~0.00 | See the quota note below |
| | **Total** | | **~USD 100/mo** | ~AED 365 |
| 13 | AI Search *(not deployed)* | Basic | *73.73* | See below |

### Why a D-series node, when a B-series would be half the price

A VM size has to pass **two independent checks**, and their error messages look nothing alike.
Three attempts, in order:

| Size | Result |
|---|---|
| `Standard_B2s` | *"The VM size of Standard_B2s is not allowed in your subscription"* — the first-generation B-series is not offered here at all |
| `Standard_B2ls_v2` | Offered, but *"Insufficient vcpu quota requested 2, remaining 0"* — the `standardBsv2Family` quota is zero |
| `Standard_D2s_v3` | Offered **and** the `DSv3` family has 10 vCPU free ✓ |

So the cheap machine is the one this subscription may not create. `D2s_v3` is 2 vCPU / 8 GiB at
$0.096/hour — about $70/month, against the ~$30 a B-series would have cost.

**That matters less than it looks**, because this group is torn down after verification:
$2.30/day instead of $1.00/day, so a day or two of checking costs roughly $3 more. The 8 GiB
also gives the six always-on workloads real headroom, where the original 4 GiB sizing was tight.

Raising the B-series quota is free, but it is a support request with an unpredictable wait.

```bash
# What this subscription may actually run, before picking a size:
az vm list-usage -l eastus2 -o json   | python -c "import sys,json;[print(i['localName'],i['currentValue'],'/',i['limit']) for i in json.load(sys.stdin) if int(i['limit'])>0]"
```

### Two free tiers this subscription had already spent

Free tiers are **one per subscription**, and the existing system holds two of the three Wathiq
would want:

| Free tier | Status | What Wathiq does instead |
|---|---|---|
| AI Search `free` | Taken by `filingsiq-search` | **Not deployed.** `deployAiSearch=false`. The pgvector retriever from M3 keeps serving, and `app/azure/search.py` is written and tested but not paid for. |
| Content Safety `F0` | Taken by `filingsiq-contentsafety` | Deploys **S0** — pay-per-call, pennies at demo volume. |
| Document Intelligence `F0` | **Available** (the existing account is S0) | Deploys **F0**, 500 pages/month free. |

### The quota trap, and how this avoids it

Azure OpenAI capacity is granted **per subscription, per region, per model, per SKU** — not per
account. Creating a second OpenAI account is harmless; giving it a deployment that draws on a
pool something else is using is not. The existing system uses `gpt-4o` Standard (10 of 50 TPM
units) and `text-embedding-3-small` GlobalStandard (150 of 3000).

Wathiq therefore deploys **`gpt-4o-mini` Standard** (0 of 200) and **`text-embedding-3-small`
Standard** (0 of 350 — Standard, not GlobalStandard). Different pools, no contention, no way
for a Wathiq demo to throttle a working application.

Before changing `chatModelName` or a SKU in `main.dev.bicepparam`, check the headroom:

```bash
az cognitiveservices usage list -l eastus2 -o table
```

---

## Deploy

```bash
./infra/scripts/deploy.sh rg-wathiq-dev eastus2
```

Six steps, about 25 minutes, most of it AKS and PostgreSQL:

1. **Register providers** — additive and subscription-wide; makes resource *types* available
   and cannot alter an existing resource.
2. **Create the resource group**, tagged so teardown will accept it later.
3. **Deploy the Bicep** — every resource, at resource-group scope.
4. **Store the two secrets in Key Vault** — the database password and the JWT signing key.
   They are the only two secrets in the system.
5. **Build the three images in ACR** (`az acr build` builds server-side, so nothing large is
   uploaded and no local Docker daemon is needed).
6. **Install the Helm chart** and wait for it to be healthy.

## Tear down

```bash
./infra/teardown/teardown.sh rg-wathiq-dev
```

Deletes the group, then purges the soft-deleted Key Vault and Cognitive Services accounts.
That last step matters: a soft-deleted vault holds its **name** for its retention period, and a
soft-deleted OpenAI account holds its **quota allocation** — so skipping it makes the next
deployment fail for want of capacity nothing is using.

---

## How the pieces fit

```
                          ┌─────────────────────────────────┐
   your browser ──HTTPS──▶│  Service → Caddy TLS → nginx    │
                          │  Azure DNS, automatic ACME cert │
                          └────────────────┬────────────────┘
                                           │ /api
                          ┌────────────────▼────────────────┐
                          │  api  — FastAPI + LangGraph     │
                          │  worker — only with Conductor   │
                          └───┬──────────┬──────────┬───────┘
                              │          │          │
              ┌───────────────┘          │          └────────────────┐
              ▼                          ▼                           ▼
   ┌────────────────────┐   ┌─────────────────────┐   ┌──────────────────────┐
   │ 4 × MCP servers    │   │ PostgreSQL Flexible │   │  Azure services      │
   │ separate Pods,     │   │ app data, pgvector, │   │  Foundry, Doc Intel, │
   │ separate Services  │   │ LangGraph           │   │  Content Safety,     │
   │ = least privilege  │   │ checkpoints         │   │  ADLS, Monitor, ML   │
   └────────────────────┘   └─────────────────────┘   └──────────┬───────────┘
                                                                  │
                                              authenticated with ─┘
                                              the workload identity —
                                              no key, anywhere
```

The deployment prints its canonical Azure hostname when it finishes. Public HTTP, including the
raw load-balancer IP, is redirect-only; use the printed `https://...eastus2.cloudapp.azure.com/`
address for login and document traffic. Caddy renews the certificate automatically and stores its
ACME state on a persistent volume.

### Why one small node is enough

M4 built a second workflow engine: an in-process runner implementing the same `ProcessEngine`
interface as Orkes Conductor, for a machine without 2 GB to spare. That pays off here. With
`processEngine: inprocess` the whole stack — api, web and four MCP servers — requests well under
1.2 GiB, which fits beside the system pods on the selected node. The separate process worker is
rendered only when `processEngine: conductor`, because the in-process engine gives it no queue.

Running Conductor instead needs a second node and roughly doubles the compute bill. Set
`wathiq.processEngine: conductor` and `aksNodeCount: 2` if you want the Conductor UI in the
demo.

### Where the secrets are

There are two, and both live in Key Vault:

| Secret | Why it cannot be an identity |
|---|---|
| `postgres-password` | PostgreSQL Flexible Server authenticates with a password. (Entra auth for PostgreSQL exists; wiring it is a follow-up.) |
| `jwt-secret` | Signs Wathiq's own demo-mode tokens. Unused when `authBackend: entra`. |

**Every Azure service uses the workload identity instead.** A pod presents its Kubernetes
service-account token, the cluster's OIDC issuer vouches for it, Entra exchanges it for a real
token. No key for Foundry, Document Intelligence, Content Safety, Storage, Search or Azure ML
exists anywhere — not in the image, not in a manifest, not in the repository. That is why
`app/azure/credentials.py` prefers `DefaultAzureCredential` everywhere and why the Key Vault
mount carries so little.

The identity's permissions are all in one file, `modules/identity.bicep`, each with a note on
why that role and not a broader one.

---

## Files

```
infra/
├── bicep/
│   ├── main.bicep                 every resource, resource-group scope
│   ├── main.dev.bicepparam        the demo's parameters (no secrets)
│   └── modules/
│       ├── aks.bicep              cluster, workload identity, CSI driver
│       ├── cognitive.bicep        Document Intelligence and Content Safety
│       ├── identity.bicep         the identity and every role it holds
│       ├── keyvault.bicep         RBAC vault
│       ├── machinelearning.bicep  workspace + 0-node compute cluster
│       ├── monitoring.bicep       Log Analytics + Application Insights
│       ├── openai.bicep           models, on non-contended quota pools
│       ├── postgres.bicep         Flexible Server with pgvector allow-listed
│       ├── registry.bicep         ACR, admin user disabled
│       ├── search.bicep           AI Search, behind a flag, off by default
│       └── storage.bicep          ADLS Gen2, hierarchical namespace
├── helm/wathiq/                   api, web, 4 × mcp, optional Conductor worker, migration Job
├── scripts/deploy.sh              the six steps above
└── teardown/teardown.sh           four guards, then delete
```

## Checking it before you deploy

All three run in containers; nothing is installed on the host.

```bash
az bicep build --file infra/bicep/main.bicep --stdout > /dev/null
```

```bash
docker run --rm -v "$PWD/infra/helm:/charts" alpine/helm:3.16.2 lint /charts/wathiq --set image.registry=x --set workloadIdentity.clientId=x --set keyVault.name=x --set keyVault.tenantId=x --set postgres.host=x
```

```bash
docker run --rm -v "$PWD:/repo" -w /repo koalaman/shellcheck:stable infra/scripts/deploy.sh infra/teardown/teardown.sh
```

## What this is not

Stated plainly, because a demo that claims to be production-ready is worse than one that does
not:

- **The database is reachable from Azure**, protected by a password and TLS, not by a private
  endpoint. A bank deployment puts PostgreSQL behind a private endpoint in a VNet the cluster
  joins. That is a network design, not a line of Bicep. (DECISIONS #76)
- **No NetworkPolicy.** The cluster runs Cilium, so restricting which pods may reach
  `mcp-core-banking` is a dozen more lines — but it is untested, and shipping an untested
  security control is worse than naming the gap.
- **Key Vault purge protection is off**, so the demo group can actually be deleted. Production
  turns it on.
- **One node, one replica, no autoscaling.** Nothing here is highly available.
- **The Azure ML compute cluster is not created.** `AmlCompute` has its own subscription vCPU
  quota, separate from the VM quota AKS uses, and this subscription's is zero — so the cluster is
  refused and would fail the whole deployment. `deployMachineLearningCompute` is `false`. The
  workspace still deploys and is still an MLflow endpoint; *submitting* a calibration job is the
  part that needs a quota increase, which is a support request rather than a template change.

## Two things the templates learned the hard way

Both were found by deploying, not by review, and both are invisible in a template:

- **A model version can be refused by the deployment preflight while `az cognitiveservices model
  list` still advertises it.** `gpt-4o-mini 2024-07-18` was the first choice and failed exactly
  that way, after the resource group had been created. The list is not the authority.
- **Azure can rate-limit your deployments.** Several redeploys in an hour turned the Cognitive
  Services preflight into `715-123420` — *"unusual activity for your account"* — refusing the
  whole template although those resources already existed and were correct. It did not clear in
  12 minutes. `WATHIQ_SKIP_AI=1 ./infra/scripts/deploy.sh rg-wathiq-dev` deploys everything
  *except* the AI services and reads their endpoints from what is already there.
- **A VM size can be unavailable to your subscription specifically.** `Standard_B2s` is refused
  here even though it exists in the region. `az vm list-skus -l <region>` tells you what *is*
  offered.
