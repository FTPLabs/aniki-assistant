# Override hook — webrtcvad установлен через webrtcvad-wheels,
# который не регистрирует dist-info под именем 'webrtcvad'.
# Пустой hook предотвращает сбой PyInstaller при сборке.
datas = []
hiddenimports = []
