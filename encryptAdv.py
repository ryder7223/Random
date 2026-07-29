import hashlib


def cryptFile(data: bytes, key: bytes | str) -> bytearray:
	if isinstance(key, str):
		key = key.encode("utf-8")

	if len(key) == 0:
		raise ValueError("Key cannot be empty.")

	output = bytearray(len(data))
	counter = 0
	offset = 0

	while offset < len(data):
		keyStream = hashlib.sha256(
			key + counter.to_bytes(8, "little")
		).digest()

		for byte in keyStream:
			if offset >= len(data):
				break

			output[offset] = data[offset] ^ byte
			offset += 1

		counter += 1

	return output


if __name__ == "__main__":
	filePath = input("Enter file name: ")

	# Can be any length
	secretKey = input("Enter encryption key: ")

	with open(filePath, "rb") as file:
		data = file.read()

	output = cryptFile(data, secretKey)

	with open(filePath, "wb") as file:
		file.write(output)

	print("Finished.")