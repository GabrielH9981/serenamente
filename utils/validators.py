import re

def validar_cpf(cpf: str) -> bool:
    # tira tudo que não é número
    cpf = re.sub(r'\D', '', cpf)

    # tem que ter 11 dígitos
    if len(cpf) != 11:
        return False

    # rejeita CPFs com todos dígitos iguais (111.111...)
    if cpf == cpf[0] * 11:
        return False

    # primeiro dígito verificador
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    resto = soma % 11
    d1 = 0 if resto < 2 else 11 - resto

    if d1 != int(cpf[9]):
        return False

    # segundo dígito verificador
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    resto = soma % 11
    d2 = 0 if resto < 2 else 11 - resto

    if d2 != int(cpf[10]):
        return False

    return True
