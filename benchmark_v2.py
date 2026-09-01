import stim
import subprocess
import time
import os
import csv
import statistics

CSV_FILE = "metricas_trellis.csv"

def init_csv():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode='w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Maquina", "Experimento", "Distancia", "Beam", "Threads", "Repeticiones", "Tiempo_Medio_s", "Desviacion_s"])

def run_trellis_benchmark(maquina, experimento, distance, beam_size, threads, shots=1000, repeticiones=3):
    print(f"[{experimento}] d={distance}, beam={beam_size}, threads={threads} ({repeticiones} runs)...")
    
    dem_file = f"dem_d{distance}.txt"
    shots_file = f"shots_d{distance}.b8"
    out_file = f"out_d{distance}.b8"
    
    # Generar problema
    circuit = stim.Circuit.generated("surface_code:rotated_memory_z", 
                                     distance=distance, rounds=distance, 
                                     after_clifford_depolarization=0.01)
    with open(dem_file, "w") as f:
        f.write(str(circuit.detector_error_model(decompose_errors=True)))
    
    circuit.compile_detector_sampler().sample_write(shots, filepath=shots_file, format="b8")
    
    comando = [
        "./bazel-bin/src/tesseract_trellis",
        "--dem", dem_file, "--in", shots_file, "--in-format", "b8",
        "--out", out_file, "--out-format", "b8",
        "--beam", str(beam_size), "--threads", str(threads)
    ]
    
    tiempos = []
    for i in range(repeticiones):
        start_time = time.perf_counter()
        subprocess.run(comando, capture_output=True, text=True)
        tiempos.append(time.perf_counter() - start_time)
        
    tiempo_medio = statistics.mean(tiempos)
    desviacion = statistics.stdev(tiempos) if repeticiones > 1 else 0.0
    
    with open(CSV_FILE, mode='a', newline='') as f:
        csv.writer(f).writerow([maquina, experimento, distance, beam_size, threads, repeticiones, round(tiempo_medio, 4), round(desviacion, 4)])
        
    print(f"  -> OK. Media: {tiempo_medio:.4f}s (±{desviacion:.4f}s)")

# --- EJECUCIÓN DE LA MATRIZ ---
init_csv()

# CAMBIA ESTE NOMBRE al ejecutar en el otro ordenador ("Intel_i5" o "Ryzen_7000")
MAQUINA = "Intel_i5" 

# Exp 1: Escalabilidad del problema (H2)
for d in [3, 5, 7, 9]:
    run_trellis_benchmark(MAQUINA, "Exp1_Escalabilidad", distance=d, beam_size=1024, threads=1)

# Exp 2: Coste de la Frontera (H2, O4)
for b in [64, 256, 1024, 4096]:
    run_trellis_benchmark(MAQUINA, "Exp2_Frontera", distance=5, beam_size=b, threads=1)

# Exp 3: Límite del Paralelismo (H4, O5)
for t in [1, 2, 4, 8, 16]:
    run_trellis_benchmark(MAQUINA, "Exp3_Paralelismo", distance=7, beam_size=4096, threads=t)

os.system("rm dem_*.txt shots_*.b8 out_*.b8")
print("Pruebas finalizadas.")