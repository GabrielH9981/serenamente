# utils/logger.py
import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logger(name='app', log_file='app.log', level=logging.INFO):
    """
    Configura logger com rotação de arquivos
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Evita duplicação de handlers
    if logger.handlers:
        return logger
    
    # Formato do log
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Handler para arquivo (com rotação)
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    file_handler = RotatingFileHandler(
        f'logs/{log_file}',
        maxBytes=10485760,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    logger.addHandler(file_handler)
    
    # Handler para console (apenas em desenvolvimento)
    if os.environ.get('FLASK_ENV') != 'production':
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(level)
        logger.addHandler(console_handler)
    
    return logger

# Logger padrão da aplicação
app_logger = setup_logger('app', 'app.log')
error_logger = setup_logger('error', 'error.log', logging.ERROR)
