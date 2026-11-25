{{/* Names and labels shared by the templates (MKC-9). */}}

{{- define "mkc.fullname" -}}
{{- if contains .Chart.Name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "mkc.selectorLabels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "mkc.labels" -}}
{{ include "mkc.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end -}}

{{/* The image; the tag is required and must not be "latest". */}}
{{- define "mkc.image" -}}
{{- $tag := required "image.tag is required (a commit SHA)" .Values.image.tag | toString -}}
{{- if eq $tag "latest" -}}
{{- fail "image.tag must not be latest; use a commit SHA" -}}
{{- end -}}
{{- printf "%s:%s" .Values.image.repository $tag -}}
{{- end -}}

{{- define "mkc.secretName" -}}
{{- .Values.existingSecret | default (printf "%s-secrets" (include "mkc.fullname" .)) -}}
{{- end -}}

{{/* Restart the pods when the settings or the chart-built Secret change. */}}
{{- define "mkc.checksums" -}}
checksum/config: {{ include (print .Template.BasePath "/configmap.yaml") . | sha256sum }}
checksum/secret: {{ include (print .Template.BasePath "/secret.yaml") . | sha256sum }}
{{- end -}}
