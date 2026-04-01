{{/*
Expand the name of the chart.
*/}}
{{- define "workflow-platform.name" -}}
{{- .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "workflow-platform.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "workflow-platform.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/instance: {{ .Release.Name }}
environment: {{ .Values.global.environment }}
{{- end }}

{{/*
API selector labels
*/}}
{{- define "workflow-platform.api.selectorLabels" -}}
app.kubernetes.io/name: workflow-api
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Worker selector labels
*/}}
{{- define "workflow-platform.worker.selectorLabels" -}}
app.kubernetes.io/name: workflow-worker
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Image reference helper — prepends registry if set
*/}}
{{- define "workflow-platform.image" -}}
{{- $registry := .Values.global.imageRegistry -}}
{{- $repo := .repo -}}
{{- $tag := .tag -}}
{{- if $registry -}}
{{- printf "%s/%s:%s" $registry $repo $tag -}}
{{- else -}}
{{- printf "%s:%s" $repo $tag -}}
{{- end -}}
{{- end }}
