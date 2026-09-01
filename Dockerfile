FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    build-essential \
    python3 \
    python3-pip \
    python3-dev \
    git \
    curl \
    valgrind \
    linux-tools-common \
    linux-tools-generic \
    && rm -rf /var/lib/apt/lists/*

# Instalar Bazelisk (gestor de Bazel)
RUN curl -L https://github.com/bazelbuild/bazelisk/releases/download/v1.19.0/bazelisk-linux-amd64 -o /usr/local/bin/bazel \
    && chmod +x /usr/local/bin/bazel

# Instalar librerías auxiliares de Python para la validación
RUN pip3 install stim numpy

WORKDIR /app