# 3D PAWS

3d-paws es una biblioteca Python3 que permite controlar los varios sensores de las estaciones meteorológicas [3D-PAWS](https://sites.google.com/ucar.edu/3dpaws/home), como los sensores BMP280, BME280, HTU21d, MCP9808, AS5600, 55300-00-02-A, SS451A y STH31D. El software se debe instalar en la Raspberry Pi 3b, 3b+ o 4 que controlará los sensores, los procesos de adquisición, archivo y procesamiento de datos, y las comunicaciones con los servidores de datos remotos. Las comunicaciones remotas se pueden lograr por medio de una red inalámbrica o de módem celular.

In English: https://github.com/3d-paws/3D-PAWS-Raspberry-Pi

## 1) Para comenzar
El sistema operativo (SO) y el software 3d_paws están grabados en una imagen de disco. Recomendamos utilizar dicha imagen para configurar la Raspberry Pi. Para hacerlo, siga estos pasos:

1. En cualquier tipo de computadora, descargue la imagen del [sistema operativo](https://drive.google.com/file/d/115t75Z_Ava5XONaAJEYmVe27xC-teYVj/view?usp=sharing) y el programa de grabación [Balena Etcher](https://etcher.balena.io/#download-etcher). 

2. Extraiga la imagen del sistema operativo del archivo .zip.

3. Inserte en la computadora una tarjeta microSD con una capacidad mínima de 32 GB, para lo cual es probable que necesite un adaptador de microSD a USB.

4. Abra Etcher y escoja Flash from File (instalar desde un archivo). Navegue al archivo .zip que contiene la imagen comprimida; busque el archivo .img en esa misma carpeta (a veces, para verlo hay que cambiar la opción Image files a All files en la parte inferior de la ventana de búsqueda) y seleccione la tarjeta SD como destino. Tenga en cuenta que la tarjeta microSD debe contar con un mínimo de 32 GB de espacio disponible.

5. Haga clic en Flash! para grabar la imagen del sistema operativo.

6. Una vez finalizado el proceso, inserte la tarjeta microSD en una Raspberry Pi y enciéndala. Si la Raspberry Pi está conectada a monitor, teclado y ratón, arrancará en un entorno de escritorio. Abra una terminal de comandos, cerciórese de que la terminal se abra en /home/pi —la ubicación por omisión cuando se abre una ventana de terminal— y luego teclee sudo python3 update_3d_paws.py

## 2) Configuración de las variables
Si bien el software se puede ejecutar sin necesidad de hacer cambios, para asegurar la exactitud de los datos recomendamos configurar al menos el nivel de presión y la altitud. También conviene activar CHORDS para que la información se transmita a la base de datos. Esto se puede hacer de dos maneras.

Método recomendado: arranque la interfaz gráfica (GUI) mediante el atajo provisto en el escritorio. El botón de configuración (Settings) en la izquierda superior de la GUI brinda acceso a 3 opciones. Haga clic en cada una de ellas y cambie las variables según corresponda. Encontrará descripciones de estas variables en la GUI.

Otro método: haga los cambios directamente en el archivo variables.txt ubicado en el escritorio del sistema (/home/pi/Desktop). Este archivo está estructurado de la manera siguiente:

    1. El intervalo de grabación (recording interval) es la frecuencia de grabación local de los datos, en minutos.
    2. El intervalo de Chords es la frecuencia de envío de los datos a CHORDS, en minutos.
    3. Fije el valor en On u Off, según desee o no enviar los datos a CHORDS.
    4. El identificador (ID) de la estación.
    5. El enlace al sitio CHORDS correcto.
    6. El nivel de presión de la estación.
    7. Fije el valor en On u Off para activar o desactivar el modo de prueba de la estación; en este modo los datos se registran a intervalos de segundos (en lugar de un minuto), de acuerdo con el intervalo de registro (Recording interval).
    8. La altitud de la estación. Por omisión, esta variable está configurada en un valor enorme; ¡asegúrese de introducir el valor correcto!

Mantenga el formato de lista separada por comas, sin introducir espacios. 

## 3) Configuración de Teamviewer
TeamViewer permite establecer una conexión remota con la Raspberry Pi. Si en algún momento surge un problema y usted necesita asistencia, normalmente este programa nos permite ayudar, de modo que es importante configurarlo. En primer lugar, abra una terminal de comandos y ejecute esta secuencia de instrucciones para generar un identificador (ID) de TeamViewer.

```bash
sudo systemctl stop teamviewerd
sudo rm -rf /etc/teamviewer/global.conf
sudo rm -rf /var/lib/teamviewer/config/global.conf
sudo rm /etc/machine-id
sudo systemd-machine-id-setup
sudo systemctl start teamviewerd
```

Cuando termine, haga clic en el icono azul en la región inferior derecha del escritorio para abrir TeamViewer. Luego, haga clic en el icono de engranaje para abrir la ventana de configuración. (Si la ventana emergente Set easy access está abierta, puede hacer clic en el engranaje allí para acceder a la ventana de configuración). Ahora abra la pestaña Advanced y desplácese hacia abajo hasta Personal Password. Teclee la contraseña personal que desea usar, haga clic en Apply para implementarla y, finalmente, haga clic en OK. Anote su identificador de Teamviewer para cuando necesite conectarse.

## 4) Control de la estación
### Activación de los sensores
Abra la GUI desde el escritorio y «active» cada sensor que desee poner en marcha. Si es preciso rearrancar el sistema, la GUI se lo indicará.

### Visualización remota
Existen varias maneras posibles de acceder a la Raspberry Pi en forma remota. Si bien
recomendamos usar el software TeamViewer que acaba de configurar, también puede hacerlo
de estas dos maneras:
*con la línea de comandos segura o SSH (Secure Shell); necesitará la dirección IP de la Raspberry Pi.
    *nombre de usuario: pi
    *contraseña: Wrf2Pi8!
*con AnyDesk (necesitará el identificador de AnyDesk para la Raspberry Pi)
    *contraseña: 3d_paws!

### Ejecución de pruebas
Abra una ventana de terminal y navegue a la ubicación de los guiones o script.
```bash
cd /3d-paws/scripts/sensors
```

Esta carpeta contiene los guiones de todos los sensores. Puede ejecutar cualquiera de ellos tecleando el comando sudo python3 seguido por el nombre del guion. Por ejemplo:
```bash
sudo python3 bmp_bme.py
```

Tenga presente que mientra lo haga el sensor de lluvia y los dos sensores del viento mostrarán datos cada minuto. Puede agregar un número tras el comando para que el código se ejecute después de esa cantidad de segundos. Por ejemplo, para probar el funcionamiento de la cubeta basculante cada 5 segundos, teclee:
```bash
sudo python3 rain.py 5
```

Si desea ejecutar todos los sensores a intervalos de menos de un minuto, puede activar el modo de prueba. En dicho modo, la estación no transmite a CHORDS, el valor de intervalo se interpreta en segundos en lugar de minutos y todos los datos registrados se almacenan en la subcarpeta tests/ de la carpeta data/. 

El modo de prueba se puede activar en el menú Intervals de la GUI o cambiando a true el séptimo valor de variables.txt. Es posible que necesite rearrancar la Raspberry Pi para que los cambios surtan efecto (lo mismo vale al desactivar el modo de prueba).

### Ubicación de los datos
Si las opciones correspondientes están activadas, la Raspberry Pi transmitirá los datos a CHORDS y los respaldará en el servidor de RAL. Para consultar los datos locales, búsquelos en /home/pi/data/. Los datos obtenidos en el transcurso de un período de 24 horas se almacenan en un único archivo.

## Actualizaciones
Si un sensor no registra datos, siga estos pasos para identificar y solucionar el problema:

1. Actualice el software (siga las instrucciones proporcionadas antes).

2. Asegúrese de que el sensor esté conectado. Abra la línea de comandos y teclee

```bash
i2cdetect -y 0
```

Si la dirección del sensor no figura en la lista, no está enchufado correctamente. Revise las conexiones. A continuación se muestran las direcciones de los sensores. Si un sensor no aparece en la lista, no es compatible con el protocolo I2C y no se puede detectar de esta manera.
*MCP9808: 0x18 
*HTU21D: 0x40 
*SHT31d: 0x44 or 0x45
*SI1145: 0x60
*BMP/BME 280: 0x77

3. Fíjese si están grabando los datos.

```bash
cd /home/pi/3d_paws/scripts/sensors/
```

Ejecute el guion para ese sensor. Por ejemplo:
```bash
sudo python3 mcp9808.py
```

Observe que al hacerlo se duplicarán los datos registrados. Considere la posibilidad de apagar el sensor en la GUI.

4. Fíjese si hay algún problema con el guion de transmisión. 

```bash
cd /home/pi/3d_paws/scripts/upkeep/
sudo python3 report.py
```

5. Todo error que ocurra se resistrará en archivos de bitácora en /tmp. Por ejemplo, para examinar el archivo de bitácora del sensor HTU21d, teclee:

```bash
cd /tmp
more htu21d.log
```

6. Si no logra solucionar el problema, envíe un mensaje tanto a Paul Kucera (pkucera@ucar.edu) como a Joey Rener (jrener@ucar.edu) para obtener asistencia.

## License
[MIT](https://choosealicense.com/licenses/mit/)