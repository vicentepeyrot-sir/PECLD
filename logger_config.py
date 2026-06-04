# -*- coding: utf-8 -*-
import logging
import os
import sys

from config import dir_path


def setup_logger():
    """Configura o sistema de log para salvar em arquivo e exibir no console."""
    log_file = os.path.join(dir_path, 'app.log')

    log_format = logging.Formatter(
        '%(asctime)s - [%(levelname)s] - (%(name)s) - %(message)s',
        datefmt='%d-%m-%Y %H:%M:%S'
    )

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        # Handler para arquivo
        file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
        file_handler.setFormatter(log_format)
        logger.addHandler(file_handler)

        # Handler para console com flush imediato
        class Unbuffered:
            def __init__(self, stream):
                self.stream = stream
            def write(self, data):
                self.stream.write(data)
                self.stream.flush()
            def writelines(self, datas):
                self.stream.writelines(datas)
                self.stream.flush()
            def __getattr__(self, attr):
                return getattr(self.stream, attr)

        stream_handler = logging.StreamHandler(Unbuffered(sys.stdout))
        stream_handler.setFormatter(log_format)
        logger.addHandler(stream_handler)
