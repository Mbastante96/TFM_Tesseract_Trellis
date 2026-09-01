import stim
import subprocess
import time
import os
import csv

# Nombre del archivo donde se guardarán los resultados
CSV_FILE = "metricas_trellis.csv"

def init_csv():
    # Escribir la cabecera si el archivo no existe
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode='w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Distancia", "Rondas", "Shots", "Beam", "Threads", "Tiempo_Total_s", "Latencia_ms"])

def run_trellis_benchmark(distance, rounds, shots, beam_size, threads):
    print(f"\n--- Ejecutando d={distance}, shots={shots}, beam={beam_size}, threads={threads} ---")
    
    dem_file = f"dem_d{distance}.txt"
    shots_file = f"shots_d{distance}.b8"
    out_file = f"out_d{distance}.b8"
    
    # 1. Generar el circuito y el modelo de error
    circuit = stim.Circuit.generated("surface_code:rotated_memory_z", 
                                     distance=distance, rounds=rounds, 
                                     after_clifford_depolarization=0.01)
    
    dem = circuit.detector_error_model(decompose_errors=True)
    with open(dem_file, "w") as f:
        f.write(str(dem))
        
    # 2. Generar disparos (shots) y guardarlos en formato binario (.b8)
    sampler = circuit.compile_detector_sampler()
    sampler.sample_write(shots, filepath=shots_file, format="b8")
    
    # 3. Preparar la invocación al ejecutable C++
    comando = [
        "./bazel-bin/src/tesseract_trellis",
        "--dem", dem_file,
        "--in", shots_file,
        "--in-format", "b8",
        "--out", out_file,
        "--out-format", "b8",
        "--beam", str(beam_size),
        "--threads", str(threads)
    ]
    
    # 4. Medir solo el tiempo del decodificador C++
    start_time = time.perf_counter()
    resultado = subprocess.run(comando, capture_output=True, text=True)
    end_time = time.perf_counter()
    
    if resultado.returncode != 0:
        print(f"Error en C++ para d={distance}: {resultado.stderr}")
        return
        
    tiempo_total = end_time - start_time
    latencia_ms = (tiempo_total / shots) * 1000
    
    print(f"Tiempo total: {tiempo_total:.4f} s")
    print(f"Latencia por shot: {latencia_ms:.4f} ms")

    # 5. Guardar en el CSV
    with open(CSV_FILE, mode='a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([distance, rounds, shots, beam_size, threads, round(tiempo_total, 4), round(latencia_ms, 4)])
        
    print(f"  -> Guardado en CSV metricas_trellis.csv.\n")

# --- BLOQUE PRINCIPAL ---
init_csv()
# EXPERIMENTO 1: Demostrar la escalabilidad (Objetivo O4 / Hipótesis H2)
# Mantenemos el beam y los threads fijos, variamos la distancia del código.
distancias = [3, 5, 7]
tamanos_beam = [1024]
hilos = [1]

for d in distancias:
    for beam in tamanos_beam:
        for t in hilos:
            run_trellis_benchmark(distance=d, rounds=d, shots=1000, beam_size=beam, threads=t)

# Limpieza de archivos temporales pesados
os.system("rm dem_*.txt shots_*.b8 out_*.b8")
print(f"Pruebas finalizadas. Resultados guardados en {CSV_FILE}")
