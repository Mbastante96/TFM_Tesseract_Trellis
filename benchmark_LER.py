import stim
import subprocess
import time
import os
import csv
import statistics
import re

# ==========================================
# CONFIGURACIÓN GENERAL
# ==========================================
CSV_METRICAS = "metricas.csv"
BINARY_PATH = "./bazel-bin/src/tesseract_trellis"

def init_csv():
    if not os.path.exists(CSV_METRICAS):
        with open(CSV_METRICAS, mode='w', newline='') as f:
            csv.writer(f).writerow(["Maquina", "Experimento", "Circuito", "Beam", "Threads", "Repeticiones", 
                                    "Tiempo_Medio_s", "Desviacion_s", "Errores_Logicos", "LER"])

def buscar_circuito(r, d, p, nkd_interior):
    carpeta = "testdata/bivariatebicyclecodes"
    if not os.path.exists(carpeta):
        print(f"ERROR CRÍTICO: No se encuentra la carpeta '{carpeta}'. ¿Estás en la raíz del repositorio?")
        return None
        
    for archivo in os.listdir(carpeta):
        if f"r={r}," in archivo and f"d={d}," in archivo and f"p={p}," in archivo and f"nkd=[[{nkd_interior}]]" in archivo:
            return os.path.join(carpeta, archivo)
            
    print(f"No se encontró ningún archivo con r={r}, d={d}, p={p}, nkd=[[{nkd_interior}]]")
    return None

def run_full_benchmark(maquina, experimento, filepath_circuito, beam_size, threads, shots=1000, repeticiones=3):
    if not filepath_circuito or not os.path.exists(filepath_circuito):
        print(f"ERROR: No se encontró el circuito: {filepath_circuito}")
        return

    base_name = os.path.basename(filepath_circuito).replace(".stim", "")
    print(f"\n[{experimento}] Circuito={base_name[:30]}..., beam={beam_size}, threads={threads}")
    
    dem_file = f"dem_{base_name[:20]}.txt"
    shots_1000_file = f"shots_1000_{base_name[:20]}.b8"
    obs_1000_file = f"obs_1000_{base_name[:20]}.b8"
    out_file = f"out_{base_name[:20]}.b8"
    
    # -------------------------------------------------------------------------
    # 1. CARGA DEL CIRCUITO Y FILTRADO DE OBSERVABLES
    # -------------------------------------------------------------------------
    circuit_raw = stim.Circuit.from_file(filepath_circuito)
    
    circuit = stim.Circuit()
    for inst in circuit_raw.flattened():
        if inst.name == "OBSERVABLE_INCLUDE":
            if int(inst.gate_args_copy()[0]) == 0:  # Conservamos SOLO el observable L0
                circuit.append(inst)
        else:
            circuit.append(inst)

    # Generamos el DEM aceptando que habrá hiperaristas en los qLDPC
    with open(dem_file, "w") as f:
        f.write(str(circuit.detector_error_model(decompose_errors=True, ignore_decomposition_failures=True)))
    
    # -------------------------------------------------------------------------
    # 2. GENERACIÓN DE DISPAROS (SHOTS)
    # -------------------------------------------------------------------------
    sampler = circuit.compile_detector_sampler()
    sampler.sample_write(shots, filepath=shots_1000_file, format="b8", 
                         obs_out_filepath=obs_1000_file, obs_out_format="b8")
    
    # -------------------------------------------------------------------------
    # 3. FASE DE RENDIMIENTO (TIEMPO Y LER)
    # -------------------------------------------------------------------------
    comando_tiempo = [
        BINARY_PATH, 
        "--dem", dem_file, 
        "--in", shots_1000_file, "--in-format", "b8",
        "--obs_in", obs_1000_file, "--obs-in-format", "b8",
        "--out", out_file, "--out-format", "b8",
        "--beam", str(beam_size), "--threads", str(threads),
        "--print-stats"
    ]
    
    tiempos = []
    output_str = ""
    for _ in range(repeticiones):
        start_time = time.perf_counter()
        result = subprocess.run(comando_tiempo, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"ERROR CRÍTICO EN C++:")
            print(result.stderr.strip())
            return
            
        tiempos.append(time.perf_counter() - start_time)
        output_str = result.stdout
        
    t_medio = statistics.mean(tiempos)
    desviacion = statistics.stdev(tiempos) if repeticiones > 1 else 0.0

    errores_logicos = int(re.search(r"num_errors = (\d+)", output_str).group(1)) if re.search(r"num_errors = (\d+)", output_str) else 0
    ler = errores_logicos / shots
    
    with open(CSV_METRICAS, mode='a', newline='') as f:
        csv.writer(f).writerow([maquina, experimento, base_name[:20], beam_size, threads, repeticiones, 
                                round(t_medio, 4), round(desviacion, 4), errores_logicos, ler])
    print(f"  -> Tiempo: {t_medio:.4f}s| Errores lógicos: {errores_logicos} | LER: {ler:.4f}")
    
    # Limpieza de archivos temporales
    for file_to_delete in [dem_file, shots_1000_file, obs_1000_file, out_file]:
        try: os.remove(file_to_delete)
        except OSError: pass


# ==========================================
# CONFIGURACIÓN DEL EXPERIMENTO
# ==========================================
if __name__ == "__main__":
    init_csv()

    #Parámetros
    MAQUINA = "HPC" 
    R = 6
    D = 6
    P = 0.001
    NKD = "72,12,6"
    BEAM_SIZE = 1024
    THREADS = 1
    SHOTS = 1000
    REPETICIONES = 3
    NOMBRE_EXPERIMENTO = "LER_Tiempo"

    # Circuito
    circuito = buscar_circuito(r=R, d=D, p=P, nkd_interior=NKD)
    if not circuito:
        print("Circuito no encontrado")
        exit(1)

    # Ejecución
    run_full_benchmark(maquina=MAQUINA, experimento=NOMBRE_EXPERIMENTO, filepath_circuito=circuito,
                       beam_size=BEAM_SIZE, threads=THREADS, shots=SHOTS, repeticiones=REPETICIONES)

    print("\nExperimento finalizado")