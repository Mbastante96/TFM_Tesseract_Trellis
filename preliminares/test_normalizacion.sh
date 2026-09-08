#!/bin/bash

OUTPUT_FILE="resultado_normalizacion.txt"

{
echo "========================================================="
echo "  TEST DE CONSISTENCIA DE NORMALIZACIÓN DE MASAS"
echo "========================================================="

echo -e "\n--- Ejecución 1: Sin poda efectiva (Beam: 10000) ---"
../bazel-bin/src/tesseract_trellis \
  --dem circuito_r6.dem \
  --in shots_r6.b8 \
  --in-format b8 \
  --beam 10000

echo -e "\n--- Ejecución 2: Poda extrema (Beam: 2) ---"
../bazel-bin/src/tesseract_trellis \
  --dem circuito_r6.dem \
  --in shots_r6.b8 \
  --in-format b8 \
  --beam 2

echo -e "\n========================================================="
echo "  TEST FINALIZADO"
echo "========================================================="
} 2>&1 | tee "$OUTPUT_FILE"

echo -e "\nEl resultado se ha guardado correctamente en '$OUTPUT_FILE'."