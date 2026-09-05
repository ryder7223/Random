import pymem
import pymem.process
import pymem.exception
from typing import Any, cast


class Process:
	def __init__(self, PROCESS_NAME: str):
		self.PROCESS_NAME = PROCESS_NAME
		self.pm = pymem.Pymem(self.PROCESS_NAME)

		self.moduleBase = self.getModuleBase()
		self.moduleSize = self.getModuleSize()


	def readInt(self, address: int) -> int | None:
		try:
			return cast(int, self.pm.read_int(address))
		except pymem.exception.MemoryReadError:
			return None


	def readUInt(self, address: int) -> int | None:
		try:
			return cast(int, self.pm.read_uint(address))
		except pymem.exception.MemoryReadError:
			return None


	def readFloat(self, address: int) -> float | None:
		try:
			return cast(float, self.pm.read_float(address))
		except pymem.exception.MemoryReadError:
			return None


	def readDouble(self, address: int) -> float | None:
		try:
			return cast(float, self.pm.read_double(address))
		except pymem.exception.MemoryReadError:
			return None


	def readLongLong(self, address: int) -> int | None:
		try:
			return cast(int, self.pm.read_longlong(address))
		except pymem.exception.MemoryReadError:
			return None


	def readBytes(self, address: int, length: int) -> bytes | None:
		try:
			return self.pm.read_bytes(address, length)
		except pymem.exception.MemoryReadError:
			return None


	def readShort(self, address: int) -> int | None:
		try:
			return cast(int, self.pm.read_short(address))
		except pymem.exception.MemoryReadError:
			return None


	def readUShort(self, address: int) -> int | None:
		try:
			return cast(int, self.pm.read_ushort(address))
		except pymem.exception.MemoryReadError:
			return None


	def readByte(self, address: int) -> int | None:
		try:
			return cast(int, self.pm.read_uchar(address))
		except pymem.exception.MemoryReadError:
			return None


	def readString(self, address: int, length: int) -> str | None:
		rawBytes = self.readBytes(address, length)

		if rawBytes is None:
			return None

		return rawBytes.split(b"\x00", 1)[0].decode(errors="ignore")


	def readWideString(self, address: int, length: int) -> str | None:
		rawBytes = self.readBytes(address, length)

		if rawBytes is None:
			return None

		return rawBytes.decode("utf-16-le", errors="ignore").split("\x00", 1)[0]


	def writeInt(self, address: int, value: int) -> None:
		self.pm.write_int(address, value)


	def writeUInt(self, address: int, value: int) -> None:
		self.pm.write_uint(address, value)


	def writeFloat(self, address: int, value: float) -> None:
		self.pm.write_float(address, value)


	def writeDouble(self, address: int, value: float) -> None:
		self.pm.write_double(address, value)


	def writeLongLong(self, address: int, value: int) -> None:
		self.pm.write_longlong(address, value)


	def writeBytes(self, address: int, data: bytes) -> None:
		self.pm.write_bytes(address, data, len(data))


	def writeShort(self, address: int, value: int) -> None:
		self.pm.write_short(address, value)


	def writeUShort(self, address: int, value: int) -> None:
		self.pm.write_ushort(address, value)


	def writeByte(self, address: int, value: int) -> None:
		self.pm.write_uchar(address, value)


	def isReadable(self, address: int, length: int = 1) -> bool:
		try:
			self.pm.read_bytes(address, length)
			return True
		except pymem.exception.MemoryReadError:
			return False


	def hexDump(self, address: int, length: int = 32) -> bytes | None:
		data = self.readBytes(address, length)

		if data is None:
			print(f"Could not read memory at {address:#x}")
			return None

		for offset in range(0, len(data), 16):
			chunk = data[offset:offset + 16]

			hexValues = " ".join(f"{byte:02X}" for byte in chunk)
			asciiValues = "".join(
				chr(byte) if 32 <= byte <= 126 else "."
				for byte in chunk
			)

			print(
				f"{address + offset:016X}  "
				f"{hexValues:<47}  "
				f"{asciiValues}"
			)

		return data


	def getModule(self, moduleName: str | None = None) -> Any:
		if moduleName is None:
			moduleName = self.PROCESS_NAME

		module = pymem.process.module_from_name(
			self.pm.process_handle,
			moduleName
		)

		if module is None:
			raise RuntimeError(f"Could not find module: {moduleName}")

		return module


	def getModuleBase(self, moduleName: str | None = None) -> int:
		return self.getModule(moduleName).lpBaseOfDll


	def getModuleSize(self, moduleName: str | None = None) -> int:
		return self.getModule(moduleName).SizeOfImage


	def getAddress(self, moduleName: str, offset: int) -> int:
		return self.getModuleBase(moduleName) + offset


	def tracePointer(
		self,
		startAddress: int,
		offsets: list[int]
	) -> int | None:
		currentAddress = self.readLongLong(startAddress)

		if currentAddress is None:
			return None

		print(f"Base: {currentAddress:#x}")

		for offset in offsets[:-1]:
			currentAddress += offset

			print(f"+ {offset:#x} -> {currentAddress:#x}")

			currentAddress = self.readLongLong(currentAddress)

			if currentAddress is None:
				print("Failed to dereference")
				return None

			print(f"Dereferenced -> {currentAddress:#x}")

		currentAddress += offsets[-1]

		print(f"Final address: {currentAddress:#x}")

		return currentAddress


	def resolvePointer(
		self,
		startAddress: int,
		offsets: list[int]
	) -> int | None:
		currentAddress = self.readLongLong(startAddress)

		if currentAddress is None:
			return None

		for offset in offsets[:-1]:
			currentAddress += offset

			currentAddress = self.readLongLong(currentAddress)

			if currentAddress is None:
				return None

		return currentAddress + offsets[-1]


	def readPointer(
		self,
		startAddress: int,
		offsets: list[int],
		dataType: str,
		length: int = 0
	) -> Any | None:
		finalAddress = self.resolvePointer(startAddress, offsets)

		if finalAddress is None:
			return None

		if dataType == "int":
			return self.readInt(finalAddress)

		elif dataType == "uint":
			return self.readUInt(finalAddress)

		elif dataType == "float":
			return self.readFloat(finalAddress)

		elif dataType == "double":
			return self.readDouble(finalAddress)

		elif dataType == "longlong":
			return self.readLongLong(finalAddress)

		elif dataType == "bytes":
			return self.readBytes(finalAddress, length)

		elif dataType == "string":
			return self.readString(finalAddress, length)

		elif dataType == "wstring":
			return self.readWideString(finalAddress, length)

		else:
			raise ValueError(f"Unsupported data type: {dataType}")
