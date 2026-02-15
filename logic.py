from datetime import datetime
from json import load, dump, JSONDecodeError

from llama_cpp import Llama


model = Llama(
    model_path="<model path>.gguf",
    n_ctx=1024,
    verbose=False,
    temperature=0.85
)

        
def get_starter_prompt(filename='<prompt path>.txt'):
    with open(filename, encoding='utf-8') as file:
        starter_prompt = f'{file.read().encode('utf-8').decode('unicode_escape')}\n\n'
    return starter_prompt

def get_history(msg):
    userid, username = str(msg.from_user.id), msg.from_user.username
    data = read_data()
    history = ''.join(data[userid][username]['history'])   
    return history

def get_tokens(msg, model=model):
    history = get_history(msg)
    return len(model.tokenize(history.encode("utf-8"), add_bos=False))


def read_data(filename='data.json'):
    with open('data.json', encoding='utf-8') as file:
        try: data = load(file)
        except JSONDecodeError: data = {}
    return data

def write_data(data, filename='data.json'):
    with open('data.json', 'w', encoding='utf-8') as file:
        dump(data, file, ensure_ascii=False, indent=4)
        

def upd_names(msg, bot_old, user_old, bot_new, user_new, filename='data.json'):
    userid, username = str(msg.from_user.id), msg.from_user.username
    data = read_data()
    
    data[userid][username]['bot alias'] = bot_new
    data[userid][username]['user alias'] = user_new
    starter_prompt = data[userid][username]['history'][0]
    starter_prompt = starter_prompt.replace(bot_old, bot_new)
    starter_prompt = starter_prompt.replace(user_old, user_new)
    data[userid][username]['history'][0] = starter_prompt
    
    for i, story in enumerate(data[userid][username]['history']):
        if i == 0: continue
        if f'{bot_old}: ' in story: data[userid][username]['history'][i] = story.replace(f'{bot_old}: ', f'{bot_new}: ')
        elif f'{user_old}: ' in story: data[userid][username]['history'][i] = story.replace(f'{user_old}: ', f'{user_new}: ')
        
    write_data(data)
    
def trim_history(msg, model=model):
    limit = model.n_ctx() - 256
    if get_tokens(msg, model) > limit:
        userid, username = str(msg.from_user.id), msg.from_user.username
        data = read_data()
        
        new_history = [data[userid][username]['history'][0]]
        for story in reversed(data[userid][username]['history'][1:]):
            if len(model.tokenize(''.join(new_history + [story]).encode("utf-8"), add_bos=False)) > limit:
                break
            new_history.insert(1, story)
        data[userid][username]['history'] = new_history
        
        write_data(data)
    
def add_history(msg, content, trim=True, model=model, filename='data.json'):
    userid, username = str(msg.from_user.id), msg.from_user.username
    data = read_data()
    data[userid][username]['history'].append(content)
    write_data(data)
    if trim: trim_history(msg)
    
def add_log(msg, role, content, filename='data.json'):
    userid, username = str(msg.from_user.id), msg.from_user.username
    data = read_data()
    data[userid][username]['log'].append({
        'timestamp': datetime.now().isoformat(),
        'role': role,
        'content': content
    })
    write_data(data)
    
def add_data(msg, role, content, filename='data.json'):
    userid, username = str(msg.from_user.id), msg.from_user.username
    
    data = read_data()
    if userid not in data:
        data[userid] = {}
        data[userid][username] = {
            'user alias': msg.from_user.first_name,
            'bot alias': 'Mistress',
            'history': [get_starter_prompt()],
            'log': []
        }
        write_data(data)
        upd_names(
            msg,
            bot_old='<bot alias>',
            user_old='<user alias>',
            bot_new=data[userid][username]['bot alias'],
            user_new=data[userid][username]['user alias']
        )
        
    add_log(msg, role, content)
    if role in {'user', 'bot'}: add_history(msg, content)
