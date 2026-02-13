def dec2bin(x: int | str) -> str:
	return bin(x)[2:] if isinstance(x, int) else bin(int(x))[2:]

def bin2dec(x: str | int) -> int:
	if isinstance(x, int):
		x = str(x)
	elif x[:2] == "0b":
		x = x[2:]
	return int(x, 2)