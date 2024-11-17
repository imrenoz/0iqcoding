from Crypto.Cipher import AES # Импортируем модуль AES для шифрования
from Crypto.Util.Padding import pad, unpad

# Функция для шифрования сообщения
def encrypt_message(message: str, key):
    cipher = AES.new(key, AES.MODE_CBC) # Создаем новый шифр AES в режиме CBC
    return cipher.encrypt(pad(message.encode(), AES.block_size)), cipher.iv # Шифруем сообщение и возвращаем шифртекст и инициализационный вектор (IV)

# Функция для дешифрования сообщения
def decrypt_message(encrypted_message, key, iv):
    cipher = AES.new(key, AES.MODE_CBC, iv=iv)
    return unpad(cipher.decrypt(encrypted_message), AES.block_size).decode()

# Функция для шифрования содержимого файла
def encrypt_file(file, path, key):
    cipher = AES.new(key, AES.MODE_CBC)
    iv = cipher.iv

    plaintext = file.read()
    ciphertext = cipher.encrypt(pad(plaintext, AES.block_size))

    with open(path, 'wb') as output_file:
        output_file.write(iv)
        output_file.write(ciphertext)
    output_file.close()
    return len(ciphertext)

def decrypt_file(file_path, path, key):
    with open(file_path, 'rb') as input_file:
        iv = input_file.read(16) # Читаем первые 16 байт для IV
        ciphertext = input_file.read()

    cipher = AES.new(key, AES.MODE_CBC, iv)
    decrypted_data = unpad(cipher.decrypt(ciphertext), AES.block_size)

    with open(path, 'wb') as output_file: # Открываем новый файл для записи расшифрованных данных
        output_file.write(decrypted_data) # Записываем расшифрованные данные
    output_file.close()
