import subprocess

# 1. Crear un modelo DEM ambiguo
# Dos mecanismos al 50%: uno activa D0 y L0, el otro solo D0.
dem_text = """error(0.5) D0 L0
error(0.5) D0
"""
with open("ambiguo.dem", "w") as f:
    f.write(dem_text)

# 2. Crear un shot donde el detector D0 está activado (formato 01 ASCII)
with open("ambiguo.shots", "w") as f:
    f.write("1\n")

# 3. Ejecutar Tesseract Trellis
cmd = [
    "../bazel-bin/src/tesseract_trellis",
    "--dem", "ambiguo.dem",
    "--in", "ambiguo.shots",
    "--in-format", "01",
    "--beam", "100" # Beam holgado
]

print("--- TEST SÍNDROME AMBIGUO ---")

# Ejecutamos capturando la salida
resultado = subprocess.run(cmd, capture_output=True, text=True)

# Imprimimos la salida en la consola para verla al instante
print(resultado.stdout)
if resultado.stderr:
    print("ERRORES:\n", resultado.stderr)

# 4. Guardamos la evidencia en un archivo de texto
with open("resultado_ambiguo.txt", "w") as f:
    f.write("--- TEST SÍNDROME AMBIGUO ---\n")
    f.write(resultado.stdout)
    if resultado.stderr:
        f.write("\nERRORES:\n")
        f.write(resultado.stderr)

print("El resultado se ha guardado correctamente en 'resultado_ambiguo.txt'.")