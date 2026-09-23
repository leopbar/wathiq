{{/*
Shared naming and label helpers.

`wathiq.env` is the one worth reading: every workload gets the same environment, so the API,
the worker and a one-off migration Job cannot disagree about which database or which Azure
endpoint they are talking to. A migration that ran against a different database than the API
reads is the kind of bug that takes a day to find.
*/}}

{{- define "wathiq.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Block API and worker startup until the one migration Job has brought the database to every
Alembic head. The Job and Deployments are ordinary release resources, so the ServiceAccount
and SecretProviderClass exist before any pod starts. `alembic current --check-heads` is a
read-only check: several init containers may run it safely while exactly one Job migrates.
*/}}
{{- define "wathiq.waitForMigration" -}}
- name: wait-for-migration
  image: {{ include "wathiq.image" (dict "root" . "name" "wathiq-api") }}
  imagePullPolicy: {{ .Values.image.pullPolicy }}
  command:
    - /bin/sh
    - -c
    - until alembic current --check-heads; do echo "waiting for database migration"; sleep 3; done
  env:
    {{- include "wathiq.env" . | nindent 4 }}
  resources:
    requests:
      cpu: 25m
      memory: 96Mi
    limits:
      cpu: 200m
      memory: 256Mi
  securityContext:
    {{- include "wathiq.securityContext" . | nindent 4 }}
  volumeMounts:
    - name: tmp
      mountPath: /tmp
    {{- if .Values.keyVault.enabled }}
    - name: secrets-store
      mountPath: /mnt/secrets
      readOnly: true
    {{- end }}
{{- end -}}

{{- define "wathiq.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name (include "wathiq.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "wathiq.labels" -}}
app.kubernetes.io/name: {{ include "wathiq.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
{{- end -}}

{{- define "wathiq.selectorLabels" -}}
app.kubernetes.io/name: {{ include "wathiq.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/*
The image reference. Fails the render — rather than deploying something wrong — when the
registry has not been set, because the default would otherwise be an unqualified name that
Kubernetes resolves against Docker Hub.
*/}}
{{- define "wathiq.image" -}}
{{- $registry := required "image.registry must be set (the ACR login server)" .root.Values.image.registry -}}
{{- $tag := default (.root.Values.image.tag | default .root.Chart.AppVersion) (get . "tag") -}}
{{- printf "%s/%s:%s" $registry .name $tag -}}
{{- end -}}

{{/*
The PostgreSQL URL, assembled from the parts.

The password is NOT here. It arrives as WATHIQ_PG_PASSWORD from the Key Vault-backed Secret and
is substituted by the container's entrypoint, so the connection string never exists as a
literal in a manifest, in `helm get values`, or in the deployment's YAML on the cluster.
*/}}
{{- define "wathiq.databaseUrlTemplate" -}}
postgresql+psycopg://{{ .Values.postgres.user }}:$(WATHIQ_PG_PASSWORD)@{{ .Values.postgres.host }}:{{ .Values.postgres.port }}/{{ .Values.postgres.database }}?sslmode={{ .Values.postgres.sslMode }}
{{- end -}}

{{/*
Every environment variable the application reads. Used by the API, the worker and the Jobs.

The Azure endpoints are passed straight through: an empty one means "this service is not
configured", the demo implementation keeps running, and the Settings screen says which one
answered. That is the same rule the MCP URLs have followed since M3.
*/}}
{{- define "wathiq.env" -}}
- name: WATHIQ_MODE
  value: {{ .Values.wathiq.mode | quote }}
- name: WATHIQ_ENVIRONMENT
  value: {{ .Values.wathiq.environment | quote }}
- name: WATHIQ_LOG_LEVEL
  value: {{ .Values.wathiq.logLevel | quote }}
- name: WATHIQ_AUTH_BACKEND
  value: {{ .Values.wathiq.authBackend | quote }}
- name: WATHIQ_PROCESS_ENGINE
  value: {{ .Values.wathiq.processEngine | quote }}
- name: WATHIQ_REVIEW_SLA_HOURS
  value: {{ .Values.wathiq.reviewSlaHours | quote }}

# --- secrets, from the Key Vault CSI mount ---
- name: WATHIQ_PG_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ include "wathiq.fullname" . }}-secrets
      key: postgres-password
- name: WATHIQ_JWT_SECRET
  valueFrom:
    secretKeyRef:
      name: {{ include "wathiq.fullname" . }}-secrets
      key: jwt-secret

# --- database ---
# `$(VAR)` is expanded by Kubernetes from an earlier entry in this same list, so the password
# is joined to the URL inside the container and never appears in the manifest.
- name: WATHIQ_DATABASE_URL
  value: {{ include "wathiq.databaseUrlTemplate" . | quote }}

# --- MCP tool servers, one Service each ---
{{- range .Values.mcpServers }}
- name: WATHIQ_MCP_{{ .name | upper | replace "-" "_" }}_URL
  value: "http://{{ $.Release.Name }}-mcp-{{ .name }}:{{ .port }}/mcp"
{{- end }}

# --- Azure services ---
- name: WATHIQ_AZURE_OPENAI_ENDPOINT
  value: {{ .Values.azure.openAiEndpoint | quote }}
- name: WATHIQ_AZURE_OPENAI_DEPLOYMENT
  value: {{ .Values.azure.openAiDeployment | quote }}
- name: WATHIQ_AZURE_OPENAI_EMBEDDING_DEPLOYMENT
  value: {{ .Values.azure.openAiEmbeddingDeployment | quote }}
- name: WATHIQ_AZURE_DOC_INTELLIGENCE_ENDPOINT
  value: {{ .Values.azure.docIntelligenceEndpoint | quote }}
- name: WATHIQ_AZURE_CONTENT_SAFETY_ENDPOINT
  value: {{ .Values.azure.contentSafetyEndpoint | quote }}
- name: WATHIQ_AZURE_SEARCH_ENDPOINT
  value: {{ .Values.azure.searchEndpoint | quote }}
- name: WATHIQ_AZURE_SEARCH_INDEX
  value: {{ .Values.azure.searchIndex | quote }}
- name: WATHIQ_AZURE_STORAGE_ACCOUNT_URL
  value: {{ .Values.azure.storageAccountUrl | quote }}
- name: WATHIQ_AZURE_STORAGE_FILESYSTEM
  value: {{ .Values.azure.storageFilesystem | quote }}
- name: WATHIQ_AZURE_MONITOR_CONNECTION_STRING
  value: {{ .Values.azure.monitorConnectionString | quote }}
- name: APPLICATIONINSIGHTS_CONNECTION_STRING
  value: {{ .Values.azure.monitorConnectionString | quote }}
- name: WATHIQ_AZURE_ML_WORKSPACE
  value: {{ .Values.azure.mlWorkspace | quote }}
- name: WATHIQ_AZURE_ML_RESOURCE_GROUP
  value: {{ .Values.azure.mlResourceGroup | quote }}
- name: WATHIQ_AZURE_ML_SUBSCRIPTION_ID
  value: {{ .Values.azure.mlSubscriptionId | quote }}
- name: WATHIQ_ENTRA_TENANT_ID
  value: {{ .Values.azure.entra.tenantId | quote }}
- name: WATHIQ_ENTRA_CLIENT_ID
  value: {{ .Values.azure.entra.clientId | quote }}
{{- end -}}

{{/*
The security context every container runs with. Non-root, no privilege escalation, every
capability dropped, root filesystem read-only.

`runAsUser: 1001` matches the `wathiq` user the Dockerfiles create. A read-only root filesystem
means anything that writes needs an explicit emptyDir — which is the point: it makes a
container that writes to disk visible in the manifest rather than a surprise.
*/}}
{{- define "wathiq.securityContext" -}}
runAsNonRoot: true
runAsUser: 1001
runAsGroup: 1001
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
capabilities:
  drop:
    - ALL
seccompProfile:
  type: RuntimeDefault
{{- end -}}
