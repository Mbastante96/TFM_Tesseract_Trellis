import os
import re
import subprocess
import sys
from datetime import datetime

import stim


# ============================================================
# CONFIGURACION
# ============================================================

BINARY_PATH = "./bazel-bin/src/tesseract_trellis"
CIRCUITS_DIR = "testdata/bivariatebicyclecodes"

# Configuracion pequeña para que la comprobación sea rapida.
R = 6
D = 6
P = 0.001
NKD = "72,12,6"

SHOTS = 10
BEAM_WIDTH = 64
THREADS = 1

DEM_FILE = "verificacion_trellis.dem"
SHOTS_FILE = "verificacion_shots.b8"
OBS_FILE = "verificacion_observables.b8"
OUT_FILE = "verificacion_predicciones.b8"
LOG_FILE = "salida_verificacion_trellis.txt"


def buscar_circuito():
    """Localiza el circuito que coincide con la configuracion indicada."""

    if not os.path.isdir(CIRCUITS_DIR):
        raise FileNotFoundError(
            f"No se encontro la carpeta '{CIRCUITS_DIR}'. "
            "Ejecuta el script desde la raiz del repositorio."
        )

    criterios = [
        f"r={R},",
        f"d={D},",
        f"p={P},",
        f"nkd=[[{NKD}]]",
    ]

    for nombre in sorted(os.listdir(CIRCUITS_DIR)):
        if all(criterio in nombre for criterio in criterios):
            return os.path.join(CIRCUITS_DIR, nombre)

    raise FileNotFoundError(
        "No se encontro un circuito que cumpla:\n"
        f"  r={R}, d={D}, p={P}, nkd=[[{NKD}]]"
    )


def extraer_metrica(nombre, salida):
    """
    Extrae una metrica obligatoria.

    Si no aparece, genera un error en lugar de asignar cero.
    """

    patron = rf"{re.escape(nombre)}\s*=\s*(\d+)"
    coincidencia = re.search(patron, salida)

    if coincidencia is None:
        raise RuntimeError(
            f"No se encontro la metrica obligatoria '{nombre}' "
            "en la salida del ejecutable."
        )

    return int(coincidencia.group(1))


def preparar_entrada(ruta_circuito):
    """
    Carga el circuito, conserva solo L0, genera el DEM
    y produce 10 shots con sus observables de referencia.
    """

    circuito_original = stim.Circuit.from_file(ruta_circuito)
    circuito_filtrado = stim.Circuit()

    for instruccion in circuito_original.flattened():
        if instruccion.name == "OBSERVABLE_INCLUDE":
            indice = int(instruccion.gate_args_copy()[0])

            if indice == 0:
                circuito_filtrado.append(instruccion)
        else:
            circuito_filtrado.append(instruccion)

    dem = circuito_filtrado.detector_error_model(
        decompose_errors=True,
        ignore_decomposition_failures=True,
    )

    with open(DEM_FILE, "w", encoding="utf-8") as fichero:
        fichero.write(str(dem))

    sampler = circuito_filtrado.compile_detector_sampler()
    sampler.sample_write(
        SHOTS,
        filepath=SHOTS_FILE,
        format="b8",
        obs_out_filepath=OBS_FILE,
        obs_out_format="b8",
    )

    return {
        "observables_originales": circuito_original.num_observables,
        "observables_filtrados": circuito_filtrado.num_observables,
        "observables_dem": dem.num_observables,
        "detectores_dem": dem.num_detectors,
    }


def ejecutar_decodificador():
    """Ejecuta Tesseract Trellis y devuelve el resultado completo."""

    comando = [
        BINARY_PATH,
        "--dem",
        DEM_FILE,
        "--in",
        SHOTS_FILE,
        "--in-format",
        "b8",
        "--obs_in",
        OBS_FILE,
        "--obs-in-format",
        "b8",
        "--out",
        OUT_FILE,
        "--out-format",
        "b8",
        "--beam",
        str(BEAM_WIDTH),
        "--threads",
        str(THREADS),
        "--print-stats",
    ]

    resultado = subprocess.run(
        comando,
        capture_output=True,
        text=True,
    )

    return comando, resultado


def guardar_registro(
    ruta_circuito,
    datos_circuito,
    comando,
    resultado,
):
    """Guarda la evidencia completa de la comprobacion."""

    with open(LOG_FILE, "w", encoding="utf-8") as fichero:
        fichero.write("VERIFICACION DE TESSERACT TRELLIS\n")
        fichero.write("=" * 60 + "\n\n")

        fichero.write(
            f"Fecha: {datetime.now().isoformat(timespec='seconds')}\n"
        )
        fichero.write(f"Circuito: {ruta_circuito}\n")
        fichero.write(f"Binario: {BINARY_PATH}\n")
        fichero.write(f"Shots: {SHOTS}\n")
        fichero.write(f"Beam: {BEAM_WIDTH}\n")
        fichero.write(f"Threads: {THREADS}\n")

        fichero.write(
            "Observables del circuito original: "
            f"{datos_circuito['observables_originales']}\n"
        )
        fichero.write(
            "Observables despues del filtrado: "
            f"{datos_circuito['observables_filtrados']}\n"
        )
        fichero.write(
            "Observables del DEM: "
            f"{datos_circuito['observables_dem']}\n"
        )
        fichero.write(
            f"Detectores del DEM: {datos_circuito['detectores_dem']}\n"
        )

        fichero.write(f"Comando: {' '.join(comando)}\n")
        fichero.write(f"Codigo de retorno: {resultado.returncode}\n")

        fichero.write("\n=== STDOUT ===\n")
        fichero.write(resultado.stdout or "[STDOUT VACIO]\n")

        fichero.write("\n=== STDERR ===\n")
        fichero.write(resultado.stderr or "[STDERR VACIO]\n")


def limpiar_temporales():
    """Elimina las entradas temporales, pero conserva el registro."""

    for ruta in [DEM_FILE, SHOTS_FILE, OBS_FILE, OUT_FILE]:
        try:
            os.remove(ruta)
        except FileNotFoundError:
            pass


def main():
    print("=" * 60)
    print("VERIFICACION REDUCIDA DE TESSERACT TRELLIS")
    print("=" * 60)

    if not os.path.isfile(BINARY_PATH):
        raise FileNotFoundError(
            f"No se encontro el binario '{BINARY_PATH}'.\n"
            "Compilalo previamente con:\n"
            "  bazel build //src:tesseract_trellis"
        )

    ruta_circuito = buscar_circuito()
    print(f"Circuito localizado: {ruta_circuito}")

    datos_circuito = preparar_entrada(ruta_circuito)

    print(
        "Observables: "
        f"original={datos_circuito['observables_originales']}, "
        f"filtrado={datos_circuito['observables_filtrados']}, "
        f"DEM={datos_circuito['observables_dem']}"
    )

    if datos_circuito["observables_dem"] != 1:
        raise RuntimeError(
            "El DEM no contiene exactamente un observable. "
            "No se continua con la verificacion."
        )

    comando, resultado = ejecutar_decodificador()

    guardar_registro(
        ruta_circuito,
        datos_circuito,
        comando,
        resultado,
    )

    if resultado.returncode != 0:
        raise RuntimeError(
            "El ejecutable termino con error.\n"
            f"Revisa el registro: {LOG_FILE}\n\n"
            f"STDERR:\n{resultado.stderr}"
        )

    # Se utiliza stdout y stderr por si las estadísticas se escriben en cualquiera de los dos flujos.
    salida_completa = resultado.stdout + "\n" + resultado.stderr

    metricas = {
        "states_expanded": extraer_metrica(
            "states_expanded",
            salida_completa,
        ),
        "states_merged": extraer_metrica(
            "states_merged",
            salida_completa,
        ),
        "frontier_width": extraer_metrica(
            "frontier_width",
            salida_completa,
        ),
        "num_errors": extraer_metrica(
            "num_errors",
            salida_completa,
        ),
    }

    print("\nMETRICAS ENCONTRADAS EXPLICITAMENTE")
    print("-" * 60)

    for nombre, valor in metricas.items():
        print(f"{nombre} = {valor}")

    print("-" * 60)
    print(f"Codigo de retorno = {resultado.returncode}")
    print(f"Registro completo = {LOG_FILE}")

    if metricas["num_errors"] == 0:
        print(
            "\nCOMPROBACION CORRECTA: el ejecutable ha emitido "
            "explicitamente 'num_errors = 0'."
        )
        print(
            "El cero no procede de un valor alternativo asignado "
            "por el script."
        )
    else:
        print(
            "\nCOMPROBACION CORRECTA: el campo num_errors aparece "
            f"explicitamente con valor {metricas['num_errors']}."
        )

    limpiar_temporales()

    print("\nRESULTADO: VERIFICACION FINALIZADA CORRECTAMENTE.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"\nERROR: {error}", file=sys.stderr)
        print(
            f"Si se creo, revisa el archivo '{LOG_FILE}'.",
            file=sys.stderr,
        )
        sys.exit(1)