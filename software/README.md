# Software de Chunche

Esta carpeta documenta la parte de software del prototipo Chunche, el sistema robotico de Mae Industries para asistencia en conservacion patrimonial.

El objetivo del software es coordinar:

- Captura de imagenes con camara Raspberry Pi.
- Analisis visual de posibles zonas deterioradas o sucias.
- Control seguro de servomotores mediante PCA9685.
- Asistencia al restaurador bajo validacion humana.
- Registro de sesiones en base de datos local.
- Generacion de reportes PDF.

## Idea General

Chunche no busca reemplazar al restaurador. El sistema funciona como una herramienta de apoyo:

```text
Obra en estacion
  -> camara captura imagen
  -> software analiza
  -> app muestra detecciones
  -> operador valida
  -> brazo posiciona herramienta de forma segura
  -> sistema genera reporte
```

## Arquitectura

El software esta pensado para correr en una Raspberry Pi 5.

Componentes principales:

- `Raspberry Pi 5`: cerebro del sistema.
- `Raspberry Pi Camera`: captura imagenes.
- `PCA9685`: controlador de servos por I2C.
- `Servomotores`: mueven brazo, pinza y modulo superior.
- `FastAPI`: interfaz web local.
- `SQLite`: base de datos local.
- `YOLO-seg`: deteccion futura realista de suciedad superficial.

## Modos De Funcionamiento

### Modo simulacion

Sirve para probar sin hardware conectado.

```bash
python -m chunche run --mode sim --host 0.0.0.0 --port 8000
```

Este modo crea una imagen simulada, detecta zonas de prueba y genera reportes sin mover servos reales.

### Modo hardware

Sirve para usar la Raspberry Pi, camara real y PCA9685.

```bash
python -m chunche run --mode hardware --host 0.0.0.0 --port 8000
```

Antes de usar este modo se debe verificar:

- Camara funcionando.
- PCA9685 detectado en I2C.
- Fuente externa de servos conectada.
- Servos con espacio libre para moverse.

## Flujo De Uso

1. Abrir la app web.
2. Crear una nueva sesion.
3. Capturar imagen inicial.
4. Analizar la imagen.
5. Revisar detecciones.
6. Validar una accion si corresponde.
7. Capturar imagen final.
8. Generar reporte PDF.

## Seguridad

El software tiene reglas de seguridad:

- No mueve servos fuera de limites configurados.
- Usa movimiento suave.
- Tiene boton de parada.
- No ejecuta restauracion critica de forma autonoma.
- Las acciones requieren validacion humana.

Para grietas, perdida de pigmento o dano serio, el robot solo asiste al restaurador. Para suciedad superficial, puede posicionarse para limpieza controlada, siempre bajo supervision.

## Configuracion Principal

La configuracion vive en:

```text
config/hardware.yaml
```

Alli se define:

- Canales de servos.
- Limites de angulo.
- Posicion `home`.
- Poses para herramientas.
- Direccion I2C del PCA9685.
- Ruta del modelo YOLO.

Canales base:

```text
0 = base
1 = hombro
2 = codo
3 = muneca
4 = rotacion de muneca
5 = pinza
6 = modulo superior
```

## Instalacion En Raspberry Pi

Instalar paquetes base:

```bash
sudo apt update
sudo apt install -y python3-venv python3-picamera2 python3-opencv i2c-tools
```

Crear entorno de Python:

```bash
cd ~/chunche
python3 -m venv .venv --system-site-packages
source .venv/bin/activate
pip install -r requirements-rpi.txt
```

Probar camara:

```bash
rpicam-still --output test.jpg
```

Probar PCA9685:

```bash
i2cdetect -y 1
```

Debe aparecer `40`.

## Pruebas Del Software

Prueba automatica:

```bash
python -m chunche self-test
```

Pruebas unitarias:

```bash
python -m unittest discover -s tests -v
```

## Deteccion Realista Con YOLO-Seg

La demo actual puede funcionar sin modelo entrenado. Para una version mas realista se propone entrenar un modelo YOLO-seg de una sola clase:

```text
suciedad_superficial
```

El modelo final debe guardarse como:

```text
models/suciedad_superficial.pt
```

Luego activar en `config/hardware.yaml`:

```yaml
vision:
  yolo_enabled: true
  yolo_model_path: models/suciedad_superficial.pt
```

Ver el paso completo en:

```text
software/YOLO_SEG_MVP.md
```

## Documentos De Esta Carpeta

- `README.md`: resumen general del software.
- `RASPBERRY_SETUP.md`: pasos para instalar y probar en Raspberry Pi.
- `YOLO_SEG_MVP.md`: plan para entrenar deteccion realista de suciedad.

