# Puesta En Marcha Del Software En Raspberry Pi

Esta guia explica como hacer funcionar la parte de software de Chunche en la Raspberry Pi.

## 1. Verificar Hardware Conectado

Antes de correr el software:

- La Raspberry Pi debe tener Raspberry Pi OS instalado.
- La camara debe estar conectada al puerto CSI.
- El PCA9685 debe estar conectado por I2C.
- Los servos deben estar conectados al PCA9685.
- Los servos deben usar fuente externa.
- Raspberry y fuente de servos deben compartir GND.

No alimentar los servos desde la Raspberry Pi.

## 2. Activar I2C

En la terminal de Raspberry:

```bash
sudo raspi-config
```

Seleccionar:

```text
Interface Options
I2C
Yes
Finish
```

Reiniciar:

```bash
sudo reboot
```

## 3. Instalar Paquetes

```bash
sudo apt update
sudo apt install -y python3-venv python3-picamera2 python3-opencv i2c-tools
```

## 4. Probar Camara

```bash
rpicam-still --output test.jpg
```

Si no sale error, la camara funciona.

## 5. Probar PCA9685

```bash
i2cdetect -y 1
```

Debe aparecer:

```text
40
```

Si no aparece, revisar:

- SDA.
- SCL.
- VCC.
- GND.
- I2C activado.

## 6. Instalar Chunche

Entrar a la carpeta del proyecto:

```bash
cd ~/chunche
```

Crear entorno:

```bash
python3 -m venv .venv --system-site-packages
source .venv/bin/activate
```

Instalar dependencias:

```bash
pip install -r requirements-rpi.txt
```

## 7. Probar En Simulacion

```bash
python -m chunche run --mode sim --host 0.0.0.0 --port 8000
```

Abrir en navegador:

```text
http://127.0.0.1:8000
```

O desde otra computadora en la misma red:

```text
http://IP_DE_LA_RASPBERRY:8000
```

Probar:

1. Nueva sesion.
2. Inicial.
3. Analizar.
4. Reporte PDF.

## 8. Probar En Hardware

Detener la app:

```text
Ctrl + C
```

Ejecutar:

```bash
python -m chunche run --mode hardware --host 0.0.0.0 --port 8000
```

Primero probar sin obra cerca.

En la app:

1. Presionar `Home`.
2. Mover cada servo poco a poco.
3. Usar `Parada` si algo se mueve raro.
4. Ajustar limites en `config/hardware.yaml` si hace falta.

## 9. Uso Completo

Cuando el hardware ya esta calibrado:

1. Poner una prueba de papel o carton.
2. Crear sesion.
3. Capturar imagen inicial.
4. Analizar.
5. Validar solo si la deteccion tiene sentido.
6. Capturar imagen final.
7. Generar reporte PDF.

## 10. Comando Final De Uso

```bash
cd ~/chunche
source .venv/bin/activate
python -m chunche run --mode hardware --host 0.0.0.0 --port 8000
```

