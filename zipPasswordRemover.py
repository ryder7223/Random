import os
import shutil
import zipfile
import pyzipper


def removeZipPassword(inputPath, outputPath, password):
    tempDirectory = '__zip_temp_extract__'

    if os.path.exists(tempDirectory):
        shutil.rmtree(tempDirectory)

    os.makedirs(tempDirectory)

    compressionMap = {}

    with pyzipper.AESZipFile(inputPath, 'r') as inputZip:
        inputZip.pwd = password.encode('utf-8')

        for info in inputZip.infolist():
            compressionMap[info.filename] = {
                'compressType': info.compress_type,
                'dateTime': info.date_time,
                'comment': info.comment,
                'externalAttr': info.external_attr,
                'createSystem': info.create_system
            }

            extractedPath = os.path.join(tempDirectory, info.filename)

            if info.is_dir():
                os.makedirs(extractedPath, exist_ok=True)
                continue

            parentDirectory = os.path.dirname(extractedPath)

            if parentDirectory:
                os.makedirs(parentDirectory, exist_ok=True)

            with inputZip.open(info.filename) as source:
                with open(extractedPath, 'wb') as target:
                    shutil.copyfileobj(source, target)

    with zipfile.ZipFile(outputPath, 'w') as outputZip:
        for root, _, files in os.walk(tempDirectory):
            for fileName in files:
                fullPath = os.path.join(root, fileName)

                archiveName = os.path.relpath(
                    fullPath,
                    tempDirectory
                )

                metadata = compressionMap[archiveName]

                zipInfo = zipfile.ZipInfo(
                    filename=archiveName,
                    date_time=metadata['dateTime']
                )

                zipInfo.compress_type = metadata['compressType']
                zipInfo.comment = metadata['comment']
                zipInfo.external_attr = metadata['externalAttr']
                zipInfo.create_system = metadata['createSystem']

                with open(fullPath, 'rb') as source:
                    fileData = source.read()

                outputZip.writestr(zipInfo, fileData)

    shutil.rmtree(tempDirectory)


if __name__ == '__main__':
    inputZipPath = input('Enter file name: ')
    password = input('Enter the zip password: ')

    baseName = os.path.splitext(inputZipPath)[0]
    outputZipPath = f'{baseName}_noPassword.zip'

    removeZipPassword(
        inputZipPath,
        outputZipPath,
        password
    )

    originalSize = os.path.getsize(inputZipPath)
    newSize = os.path.getsize(outputZipPath)

    print()
    print(f'Created: {outputZipPath}')
    print(f'Original Size: {originalSize}')
    print(f'New Size:      {newSize}')
    print(f'Difference:    {newSize - originalSize}')