def calc(*values):
    decimals = 2
    numericValues = []
    try:
        for v in values:
            if isinstance(v, str) and v.isdigit():
                decimals = int(v)
            else:
                numericValues.append(v)
        
        total = sum(numericValues)
        for value in numericValues:
            percentage = round(100 * (value / total), decimals)
            print(f"{value}: {percentage}%")
    except:
        print("Invalid input")