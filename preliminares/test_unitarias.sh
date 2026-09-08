#!/usr/bin/env bash

set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_FILE="${SCRIPT_DIR}/resultado_unitarios_trellis.txt"
TEST_TARGET="//src:tesseract_trellis_tests"

{
    echo "========================================================="
    echo "  PRUEBAS UNITARIAS DE TESSERACT TRELLIS"
    echo "========================================================="
    echo
    echo "Fecha de ejecución: $(date --iso-8601=seconds)"
    echo "Directorio: $(pwd)"
    echo "Objetivo Bazel: ${TEST_TARGET}"
    echo
} | tee "$OUTPUT_FILE"

bazel test "$TEST_TARGET" \
    --test_output=all \
    --nocache_test_results \
    2>&1 | tee -a "$OUTPUT_FILE"

BAZEL_STATUS=${PIPESTATUS[0]}

{
    echo
    echo "========================================================="
    if [ "$BAZEL_STATUS" -eq 0 ]; then
        echo "RESULTADO: TODAS LAS PRUEBAS HAN FINALIZADO CORRECTAMENTE"
    else
        echo "RESULTADO: SE HAN PRODUCIDO ERRORES EN LAS PRUEBAS"
    fi
    echo "Código de retorno de Bazel: ${BAZEL_STATUS}"
    echo "Resultado guardado en: ${OUTPUT_FILE}"
    echo "========================================================="
} | tee -a "$OUTPUT_FILE"

exit "$BAZEL_STATUS"
