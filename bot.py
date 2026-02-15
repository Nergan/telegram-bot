from logging import INFO, basicConfig
from asyncio import run

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.enums import ChatAction

from config import TOKEN # файл с Вашем токеном
from logic import (
    add_data,
    read_data,
    write_data,
    get_history,
    get_tokens,
    upd_names,
    model
)


bot = Bot(token=TOKEN)
dp = Dispatcher()


@dp.message(Command(commands=['help', 'start']))
async def clear_cmd(msg: Message):
    await bot.send_chat_action(msg.chat.id, ChatAction.TYPING)
    add_data(msg, 'cmd request', msg.text)
    txtsuccess = '''
Это хорни бот, предназначен для разного рода dirty talk
/help - вывести это сообщение
/name - посмотреть свой ник, которым Вас видит бот
/set_botname <name> - установить ник бота
/set_username <name> - установить Ваш ник
/tokens - посмотреть свои токены
/clear - очистить контекст диалога
    '''
    add_data(msg, 'cmd response', txtsuccess)
    await msg.answer(txtsuccess)
    
    
@dp.message(Command('name'))
async def name_cmd(msg: Message):
    userid, username = str(msg.from_user.id), msg.from_user.username
    await bot.send_chat_action(msg.chat.id, ChatAction.TYPING)
    add_data(msg, 'cmd request', msg.text)
    data = read_data()
    useralias = data[userid][username]['user alias']
    botalias = data[userid][username]['bot alias']
    txtsuccess = f'Ваш псевдоним: **{useralias}**\nПсевдоним бота: **{botalias}**'
    add_data(msg, 'cmd response', txtsuccess)
    await msg.answer(txtsuccess, parse_mode='MarkdownV2')


@dp.message(Command(commands=['set_botname', 'set_username']))
async def setname_cmd(msg: Message):
    userid, username = str(msg.from_user.id), msg.from_user.username
    await bot.send_chat_action(msg.chat.id, ChatAction.TYPING)
    add_data(msg, 'cmd request', msg.text)
    cmd = msg.text.strip().split()[0]
    
    if msg.text.strip() in {'/set_botname', '/set_username'}:
        txterror = f'Ошибка: не указан новый псевдоним\\!\n`{cmd} <новый псевдоним>`'
        add_data(msg, 'cmd response', txterror)
        await msg.answer(txterror, parse_mode='MarkdownV2')
        return
    
    data = read_data()   
    if cmd == '/set_botname': oldname = data[userid][username]['bot alias']
    if cmd == '/set_username': oldname = data[userid][username]['user alias']
    txtsuccess = f'Псевдоним изменён с {oldname} на {msg.text.replace(cmd, '')}'
    
    upd_names(
        msg,
        bot_old=data[userid][username]['bot alias'],
        user_old=data[userid][username]['user alias'],
        bot_new=msg.text.replace(cmd, '').strip() if cmd == '/set_botname' else data[userid][username]['bot alias'],
        user_new=msg.text.replace(cmd, '').strip() if cmd == '/set_username' else data[userid][username]['user alias']
    )
    
    add_data(msg, 'cmd response', txtsuccess)
    await msg.answer(txtsuccess)
    
    
@dp.message(Command('tokens'))
async def tokens_cmd(msg: Message):
    await bot.send_chat_action(msg.chat.id, ChatAction.TYPING)
    add_data(msg, 'cmd request', msg.text)
    tokens = get_tokens(msg)
    txtsuccess = f'Вы потратили {tokens} токенов из {model.n_ctx()}\n'
    txtsuccess += 'Токены - это память бота - то, сколько информации он способен удержать в контексте'
    add_data(msg, 'cmd response', txtsuccess)
    await msg.answer(txtsuccess)
    
    
@dp.message(Command('clear'))
async def clear_cmd(msg: Message):
    userid, username = str(msg.from_user.id), msg.from_user.username
    await bot.send_chat_action(msg.chat.id, ChatAction.TYPING)
    add_data(msg, 'cmd request', msg.text)
    data = read_data()
    del data[userid][username]['history'][1:]
    write_data(data)
    txtsuccess = f'История диалога очищена (в памяти бота)'
    add_data(msg, 'cmd response', txtsuccess)
    await msg.answer(txtsuccess)
    

@dp.message()
async def msg(msg: Message):
    try:
        await bot.send_chat_action(msg.chat.id, ChatAction.TYPING)
        prompt = msg.text
        useralias = msg.from_user.first_name
        data = read_data()
        if data: useralias = data[str(msg.from_user.id)][msg.from_user.username]['user alias']
        add_data(msg, 'user', f'{useralias}: {prompt}\n\n')
        data = read_data() # чтобы загрузить обрезанный диалог
        botalias = data[str(msg.from_user.id)][msg.from_user.username]['bot alias']
        history = get_history(msg)
        answer = model(
            f'{history}{botalias}:',
            max_tokens=120,
            echo=False,
            stop=[f'{useralias}: ', f'{botalias}: ']
        )["choices"][0]["text"]
        add_data(msg, 'bot', f'{botalias}:{answer}\n\n')
        await msg.answer(answer)
    except Exception as ex:
        await msg.answer(f'[error]\n\n{str(ex)}')


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    basicConfig(level=INFO)
    try:
        run(main())
    except KeyboardInterrupt:
        print('quit...')