# YOLO-Seg De Una Clase Para Suciedad Superficial

Este documento describe el MVP realista de vision computacional para Chunche.

La idea es entrenar un modelo de segmentacion con una sola clase:

```text
suciedad_superficial
```

Segmentacion significa que el modelo marca la forma de la suciedad, no solo un cuadro.

## 1. Por Que YOLO-Seg

Para Chunche no basta con decir:

```text
La pintura esta sucia.
```

El robot necesita saber:

```text
En que zona esta la suciedad.
Que forma tiene.
Donde esta el centro aproximado.
```

Por eso se usa segmentacion.

## 2. Herramientas

Herramientas recomendadas:

- Roboflow: etiquetado simple en navegador.
- CVAT: etiquetado mas profesional.
- Google Colab: entrenamiento con GPU.
- Ultralytics YOLO: entrenamiento y uso del modelo.
- Raspberry Pi: inferencia final.

## 3. Crear Fotos

No ensuciar pinturas reales.

Usar:

- Impresiones de pinturas.
- Carton pintado.
- Lienzos baratos.
- Acetato encima de la imagen.
- Polvo falso o manchas sobre el acetato.

Mantener siempre:

- Misma luz.
- Misma distancia.
- Camara fija.
- Fondo estable.

## 4. Cantidad De Fotos

MVP minimo:

```text
30 fotos sucias
20 fotos limpias
10 fotos dificiles
```

Mejor:

```text
150 a 300 fotos
```

Fotos dificiles son imagenes con sombras, colores oscuros o textura fuerte, pero sin suciedad real.

## 5. Etiquetado

Crear una sola clase:

```text
suciedad_superficial
```

Reglas:

- Marcar solo la suciedad.
- No marcar sombras.
- No marcar reflejos.
- No marcar textura normal.
- En fotos limpias, no marcar nada.

Usar poligonos alrededor de la zona sucia.

## 6. Exportar Dataset

Exportar en formato:

```text
YOLOv8/YOLO11 Segmentation
```

La carpeta debe tener:

```text
data.yaml
images/
labels/
```

Validar:

```bash
python tools/validate_yolo_seg_dataset.py ruta/al/dataset
```

## 7. Entrenar En Colab

Instalar Ultralytics:

```python
!pip install ultralytics
```

Entrenar:

```python
!python tools/train_yolo_seg.py \
  --data /content/dataset/data.yaml \
  --model yolo11n-seg.pt \
  --epochs 80 \
  --imgsz 640 \
  --batch 8
```

Si Colab se queda sin memoria:

```text
batch = 4
imgsz = 512
```

El modelo final queda como:

```text
runs/segment/chunche_suciedad_seg/weights/best.pt
```

Renombrar:

```text
suciedad_superficial.pt
```

## 8. Instalar Modelo En Chunche

Copiar el modelo a:

```text
models/suciedad_superficial.pt
```

Instalar dependencias YOLO:

```bash
pip install -r requirements-yolo.txt
```

Activar en `config/hardware.yaml`:

```yaml
vision:
  yolo_enabled: true
  yolo_model_path: models/suciedad_superficial.pt
```

## 9. Probar

Primero:

```bash
python -m chunche run --mode sim --host 0.0.0.0 --port 8000
```

Luego:

```bash
python -m chunche run --mode hardware --host 0.0.0.0 --port 8000
```

En la app:

1. Crear sesion.
2. Capturar imagen.
3. Analizar.
4. Ver mascara azul de suciedad.
5. Revisar confianza.
6. Validar solo si tiene sentido.
7. Generar reporte PDF.

## 10. Criterios De Exito

El MVP funciona si:

- Detecta suciedad en 8 de cada 10 imagenes sucias.
- No detecta suciedad falsa en mas de 2 de cada 10 imagenes limpias.
- Muestra mascara sobre la imagen.
- Guarda area detectada.
- Genera reporte PDF.
- No mueve el brazo sin validacion humana.

