# Diccionario de corrección ortográfica

`es_CO.aff` / `es_CO.dic`: diccionario Hunspell de español (Colombia), tomado de
[`wooorm/dictionaries`](https://github.com/wooorm/dictionaries/tree/main/dictionaries/es-CO)
(a su vez generado a partir de [`sbosio/rla-es`](https://github.com/sbosio/rla-es),
el mismo diccionario que usa LibreOffice/Apache OpenOffice).

Triple licencia GPL v3+ / LGPL v3+ / MPL v1.1+ — ver `LICENCIA.txt`. Se usa acá
bajo MPL. Lo lee `services/ortografia.py` con la librería `spylls` (Hunspell
reimplementado en Python puro, sin dependencias compiladas — más fácil de
empaquetar con PyInstaller que un binding a la librería C).

Para actualizar el diccionario: bajar `index.aff`/`index.dic` de la carpeta
`es-CO` de ese repo y reemplazar estos dos archivos (mismo nombre, misma
carpeta).
