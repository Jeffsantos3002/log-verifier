import requests
import re
import time
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import logging
from collections import deque
from flask import Flask
import threading

app = Flask(__name__)

URL = "https://bruno.dcomp.ufs.br/aulas/paa/notas/jefersonoliveira_202100045662_criptografia.log"
log_file = "/app/saida.txt"

# Configura o logging para salvar apenas em saida.txt
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8', mode='a')
    ]
)

def validate_log_content(content):
    try:
        content = content.strip()
        content = re.sub(r'^.*?(?=-{29,})', '', content, flags=re.DOTALL)
        lines = content.strip().split('\n')
        lines = [line.strip() for line in lines]
        if len(lines) != 8:
            return False, f"Número incorreto de linhas: {len(lines)}"
        if not re.match(r'^-{29,}$', lines[0]):
            return False, f"Borda superior inválida: '{lines[0]}'"
        if not re.match(r'^\|\s*\d{2}/\d{2}/\d{4}\s*@\s*\d{2}:\d{2}:\d{2}\s*\|$', lines[1]):
            return False, f"Formato de data inválido: '{lines[1]}'"
        if not re.match(r'^-{29,}$', lines[2]):
            return False, f"Separador após data inválido: '{lines[2]}'"
        if not re.match(r'^\|\s*CPU Usage:\s*\d+%\s*\|$', lines[3]):
            return False, f"Formato de CPU Usage inválido: '{lines[3]}'"
        if not re.match(r'^\|\s*Max Memory:\s*\d+\s*KB\s*\|$', lines[4]):
            return False, f"Formato de Max Memory inválido: '{lines[4]}'"
        if not re.match(r'^\|\s*Execution time:\s*\d+\.\d+\s*s\s*\|$', lines[5]):
            return False, f"Formato de Execution time inválido: '{lines[5]}'"
        if not re.match(r'^\|\s*Exit code:\s*0\s*\(success\)\s*\|$', lines[6]):
            return False, f"Exit code inválido ou não é success: '{lines[6]}'"
        if not re.match(r'^-{29,}$', lines[7]):
            return False, f"Borda inferior inválida: '{lines[7]}'"
        return True, "Log válido"
    except Exception as e:
        return False, f"Erro na validação: {str(e)}"

def check_log():
    output_buffer = deque()
    twenty_four_hours = timedelta(hours=24)
    last_log_content = ""
    
    while True:
        try:
            response = requests.get(URL)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            pre_content = soup.find('pre')
            
            current_time = datetime.now()
            log_content = ""
            pre_message = ""
            
            if pre_content:
                log_content = pre_content.get_text()
            else:
                log_content = response.text
                pre_message = f"[{current_time.strftime('%Y-%m-%d %H:%M:%S')}] Tag <pre> não encontrada, tentando conteúdo bruto"
                output_buffer.append((current_time, pre_message, log_content))
                logging.info(pre_message)
                
            is_valid, message = validate_log_content(log_content)
            
            output_buffer.append((current_time, f"[{current_time.strftime('%Y-%m-%d %H:%M:%S')}] {message}", log_content))
            
            if is_valid:
                last_log_content = log_content
            else:
                error_message = f"[{current_time.strftime('%Y-%m-%d %H:%M:%S')}] Conteúdo processado:\n{log_content}\n{'-' * 50}"
                output_buffer.append((current_time, error_message, ""))
                logging.info(error_message)
                
            while output_buffer and (current_time - output_buffer[0][0]) > twenty_four_hours:
                output_buffer.popleft()
            
            output = ["Estado do log nas últimas 24 horas:", "=" * 50]
            for timestamp, msg, content in output_buffer:
                if msg.startswith(f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S')}] Tag <pre>"):
                    output.append(msg)
                if not msg.startswith(f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S')}] Conteúdo processado") and content:
                    output.append(f"Estado do log {timestamp.strftime('%Y-%m-%d %H:%M:%S')}:")
                    output.append(content)
                if not msg.startswith(f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S')}] Tag <pre>"):
                    output.append(msg)
            output.append("=" * 50)
            
            output.append("Estado atual do log:")
            output.append(last_log_content if last_log_content else "Nenhum log válido recebido ainda")
            output.append("=" * 50)
            
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(output) + '\n')
                
        except requests.RequestException as e:
            current_time = datetime.now()
            error_message = f"[{current_time.strftime('%Y-%m-%d %H:%M:%S')}] Erro ao acessar o log: {str(e)}"
            output_buffer.append((current_time, error_message, ""))
            logging.info(error_message)
            
            while output_buffer and (current_time - output_buffer[0][0]) > twenty_four_hours:
                output_buffer.popleft()
                
            output = ["Estado do log nas últimas 24 horas:", "=" * 50]
            for timestamp, msg, content in output_buffer:
                if msg.startswith(f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S')}] Tag <pre>"):
                    output.append(msg)
                if not msg.startswith(f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S')}] Conteúdo processado") and content:
                    output.append(f"Estado do log {timestamp.strftime('%Y-%m-%d %H:%M:%S')}:")
                    output.append(content)
                if not msg.startswith(f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S')}] Tag <pre>"):
                    output.append(msg)
            output.append("=" * 50)
            
            output.append("Estado atual do log:")
            output.append(last_log_content if last_log_content else "Nenhum log válido recebido ainda")
            output.append("=" * 50)
            
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(output) + '\n')
                
        time.sleep(3600)  # 1 hora para produção

@app.route('/saida')
def get_saida():
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            return '<pre>' + f.read() + '</pre>'
    except FileNotFoundError:
        return "Arquivo saida.txt não encontrado", 404

def run_flask():
    app.run(host='0.0.0.0', port=8080)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    try:
        check_log()
    except KeyboardInterrupt:
        logging.info("Script interrompido pelo usuário.")