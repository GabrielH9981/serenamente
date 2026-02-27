import re
from email_validator import validate_email, EmailNotValidError
import phonenumbers
from typing import Optional, Tuple
from urllib.parse import urlparse


def validar_cpf(cpf: str) -> bool:
    """Valida CPF brasileiro."""
    cpf = re.sub(r'\D', '', cpf)
    
    if len(cpf) != 11:
        return False
    
    if cpf == cpf[0] * 11:
        return False
    
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    resto = soma % 11
    d1 = 0 if resto < 2 else 11 - resto
    
    if d1 != int(cpf[9]):
        return False
    
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    resto = soma % 11
    d2 = 0 if resto < 2 else 11 - resto
    
    if d2 != int(cpf[10]):
        return False
    
    return True


def validar_email(email: str) -> Tuple[bool, Optional[str]]:
    """
    Valida email.
    
    Returns:
        (valido: bool, email_normalizado: str ou None)
    """
    if not email:
        return False, None
    
    try:
        validated = validate_email(email, check_deliverability=False)
        return True, validated.normalized
    except EmailNotValidError:
        return False, None


def validar_telefone(telefone: str, regiao: str = 'BR') -> Tuple[bool, Optional[str]]:
    """
    Valida telefone.
    
    Returns:
        (valido: bool, telefone_formatado: str ou None)
    """
    if not telefone:
        return False, None
    
    try:
        parsed = phonenumbers.parse(telefone, regiao)
        if phonenumbers.is_valid_number(parsed):
            formatted = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
            return True, formatted
        return False, None
    except:
        return False, None


def validar_url(url: str) -> Tuple[bool, Optional[str]]:
    """
    Valida URL.
    
    Returns:
        (valido: bool, mensagem_erro: str ou None)
    """
    if not url:
        return True, None  # URL vazia é válida (campo opcional)
    
    url = url.strip()
    
    # Adiciona https:// se não tiver protocolo
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    try:
        result = urlparse(url)
        if all([result.scheme, result.netloc]):
            # Verifica se tem pelo menos um ponto no domínio
            if '.' in result.netloc:
                return True, url
        return False, "URL inválida"
    except:
        return False, "URL inválida"


def sanitizar_texto(texto: str, max_length: Optional[int] = None) -> str:
    """
    Sanitiza texto removendo caracteres perigosos.
    
    Args:
        texto: Texto a ser sanitizado
        max_length: Tamanho máximo (opcional)
    
    Returns:
        Texto sanitizado
    """
    if not texto:
        return ''
    
    # Remove caracteres de controle
    texto = ''.join(char for char in texto if ord(char) >= 32 or char in '\n\r\t')
    
    # Limita tamanho
    if max_length:
        texto = texto[:max_length]
    
    return texto.strip()
