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
CSV_TIEMPOS = "metricas_tiempos.csv"
CSV_RAM = "metricas_ram.csv"
MASSIF_FILE = "massif.out.tmp"
BINARY_PATH = "./bazel-bin/src/tesseract_trellis"

def init_csvs():
    if not os.path.exists(CSV_TIEMPOS):
        with open(CSV_TIEMPOS, mode='w', newline='') as f:
            csv.writer(f).writerow(["Maquina", "Experimento", "Circuito", "Beam", "Threads", "Repeticiones", 
                                    "Tiempo_Medio_s", "Desviacion_s", "Estados_Expandidos", 
                                    "Estados_Fusionados", "Max_Frontera", "Errores_Logicos", "LER"])
            
    if not os.path.exists(CSV_RAM):
        with open(CSV_RAM, mode='w', newline='') as f:
            csv.writer(f).writerow(["Maquina", "Experimento", "Circuito", "Beam", "Threads", "Pico_RAM_MB"])

def parse_massif_peak(filename):
    max_bytes = 0
    try:
        with open(filename, 'r') as f:
            for line in f:
                if line.startswith("mem_heap_B="):
                    mem = int(line.strip().split("=")[1])
                    if mem > max_bytes: 
                        max_bytes = mem
    except FileNotFoundError:
        return 0
    return max_bytes / (1024 * 1024)

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
    """Ejecuta un benchmark completo: mide tiempo, métricas internas y consumo de RAM."""
    if not filepath_circuito or not os.path.exists(filepath_circuito):
        print(f"ERROR: No se encontró el circuito: {filepath_circuito}")
        return

    base_name = os.path.basename(filepath_circuito).replace(".stim", "")
    print(f"\n[{experimento}] Circuito={base_name[:30]}..., beam={beam_size}, threads={threads}")
    
    dem_file = f"dem_{base_name[:20]}.txt"
    shots_1000_file = f"shots_1000_{base_name[:20]}.b8"
    obs_1000_file = f"obs_1000_{base_name[:20]}.b8"
    shots_10_file = f"shots_10_{base_name[:20]}.b8"
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
    sampler.sample_write(10, filepath=shots_10_file, format="b8") # Reducido para Valgrind
    
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
            print(f"  ❌ ERROR CRÍTICO EN C++:")
            print(result.stderr.strip())
            return
            
        tiempos.append(time.perf_counter() - start_time)
        output_str = result.stdout
        
    t_medio = statistics.mean(tiempos)
    desviacion = statistics.stdev(tiempos) if repeticiones > 1 else 0.0

    # Parsear resultados de la caja negra
    estados_expandidos = int(re.search(r"states_expanded = (\d+)", output_str).group(1)) if re.search(r"states_expanded = (\d+)", output_str) else 0
    estados_fusionados = int(re.search(r"states_merged = (\d+)", output_str).group(1)) if re.search(r"states_merged = (\d+)", output_str) else 0
    max_frontera = int(re.search(r"frontier_width = (\d+)", output_str).group(1)) if re.search(r"frontier_width = (\d+)", output_str) else 0
    errores_logicos = int(re.search(r"num_errors = (\d+)", output_str).group(1)) if re.search(r"num_errors = (\d+)", output_str) else 0
    ler = errores_logicos / shots
    
    with open(CSV_TIEMPOS, mode='a', newline='') as f:
        csv.writer(f).writerow([maquina, experimento, base_name[:20], beam_size, threads, repeticiones, 
                                round(t_medio, 4), round(desviacion, 4), 
                                estados_expandidos, estados_fusionados, max_frontera, errores_logicos, ler])
    print(f"  -> Tiempo: {t_medio:.4f}s | Frontera Max: {max_frontera} | LER: {ler:.4f}")

    # -------------------------------------------------------------------------
    # 4. FASE ESPACIAL (VALGRIND MASSIF - RAM)
    # -------------------------------------------------------------------------
    comando_ram = [
        "valgrind", "--tool=massif", f"--massif-out-file={MASSIF_FILE}",
        BINARY_PATH, 
        "--dem", dem_file, "--in", shots_10_file, "--in-format", "b8",
        "--beam", str(beam_size), "--threads", "1"
    ]
    
    subprocess.run(comando_ram, capture_output=True)
    pico_mb = parse_massif_peak(MASSIF_FILE)
    if os.path.exists(MASSIF_FILE):
        os.remove(MASSIF_FILE)
        
    with open(CSV_RAM, mode='a', newline='') as f:
        csv.writer(f).writerow([maquina, experimento, base_name[:20], beam_size, threads, round(pico_mb, 2)])
    print(f"  -> Memoria (Pico RAM): {pico_mb:.2f} MB")

    # Limpieza de archivos temporales
    for file_to_delete in [dem_file, shots_1000_file, obs_1000_file, shots_10_file, out_file]:
        try: os.remove(file_to_delete)
        except OSError: pass


# ==========================================
# PANEL DE CONTROL DE LA MATRIZ DEL TFM
# ==========================================
if __name__ == "__main__":
    init_csvs()
    MAQUINA = "ThinkPad_i5" 
    
    # Circuitos seguros (d <= 10, para no superar el límite de 4 words del binario)
    circuito_d6 = buscar_circuito(r=6, d=6, p=0.001, nkd_interior="72,12,6")
    circuito_d10 = buscar_circuito(r=10, d=10, p=0.001, nkd_interior="90,8,10")
    
    CIRCUITO_BASE = circuito_d10 if circuito_d10 else circuito_d6
    CIRCUITOS_ESCALABILIDAD = [c for c in [circuito_d6, circuito_d10] if c]

    print("=== INICIANDO VALIDACIÓN TFM ===")

    
    # Exp 2: Coste de la Frontera (Impacto del Beam Size)
    if CIRCUITO_BASE:
        for b in [64, 256, 1024, 2048]:
            run_full_benchmark(MAQUINA, "Exp2_Frontera", filepath_circuito=CIRCUITO_BASE, beam_size=b, threads=1, repeticiones=3)

    # Exp 3: Límite del Paralelismo
    if CIRCUITO_BASE:
        for t in [1, 2, 4, 8]: 
            run_full_benchmark(MAQUINA, "Exp3_Paralelismo", filepath_circuito=CIRCUITO_BASE, beam_size=1024, threads=t, repeticiones=3)

    # Exp 4: Variación de la Tasa de Ruido (p) para una distancia fija
    print("\n=== INICIANDO EXP 4: BARRIDO DE TASA DE RUIDO (p) ===")
    for tasa_p in [0.001, 0.005, 0.009]:
        circuito_ruido = buscar_circuito(r=6, d=6, p=tasa_p, nkd_interior="72,12,6")
        if circuito_ruido:
            run_full_benchmark(MAQUINA, "Exp4_Barrido_Ruido", filepath_circuito=circuito_ruido, beam_size=1024, threads=1, repeticiones=3)

    # Exp 1: Escalabilidad del problema (Variando distancia d <= 10)
    for circuito in CIRCUITOS_ESCALABILIDAD:
        run_full_benchmark(MAQUINA, "Exp1_Escalabilidad", filepath_circuito=circuito, beam_size=1024, threads=1, repeticiones=3)

    print("\n¡Pruebas finalizadas con éxito! Revisa metricas_tiempos.csv y metricas_ram.csv")