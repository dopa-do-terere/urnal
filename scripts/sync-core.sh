#!/usr/bin/env bash
# Copia o núcleo compartilhado (financas_core) para dentro de functions/,
# pois o Firebase só publica o conteúdo dessa pasta. Roda automaticamente
# antes de `firebase deploy` (predeploy em firebase.json); rode à mão antes
# de usar os emuladores.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
rm -rf "$root/functions/financas_core"
cp -R "$root/financas_core" "$root/functions/financas_core"
find "$root/functions/financas_core" -name "__pycache__" -prune -exec rm -rf {} +
echo "financas_core sincronizado em functions/"
