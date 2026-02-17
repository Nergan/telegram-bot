from logging import INFO, basicConfig
from asyncio import run

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ChatAction

from config import TOKEN, MAX_TOKENS
from logic import (
    add_data,
    get_history,
    get_tokens,
    upd_names,
    get_user_alias,
    get_bot_alias,
    clear_history,
    model
)

bot = Bot(token=TOKEN)
dp = Dispatcher()


@dp.message(Command(commands=['help', 'start']))
async def help_start_cmd(msg: Message):
    await bot.send_chat_action(msg.chat.id, ChatAction.TYPING)
    await add_data(msg, 'cmd request', msg.text)
    txtsuccess = '''
Это хорни бот, предназначен для разного рода dirty talk
/help - вывести это сообщение
/name - посмотреть свой ник, которым Вас видит бот
/set_botname <name> - установить ник бота
/set_username <name> - установить Ваш ник
/tokens - посмотреть свои токены
/clear - очистить контекст диалога
    '''
    await add_data(msg, 'cmd response', txtsuccess)
    await msg.answer(txtsuccess)


@dp.message(Command('name'))
async def name_cmd(msg: Message):
    await bot.send_chat_action(msg.chat.id, ChatAction.TYPING)
    await add_data(msg, 'cmd request', msg.text)
    useralias = await get_user_alias(msg)
    botalias = await get_bot_alias(msg)
    txtsuccess = f'Ваш псевдоним: **{useralias}**\nПсевдоним бота: **{botalias}**'
    await add_data(msg, 'cmd response', txtsuccess)
    await msg.answer(txtsuccess, parse_mode='MarkdownV2')


@dp.message(Command(commands=['set_botname', 'set_username']))
async def setname_cmd(msg: Message):
    await bot.send_chat_action(msg.chat.id, ChatAction.TYPING)
    await add_data(msg, 'cmd request', msg.text)
    cmd = msg.text.strip().split()[0]

    if msg.text.strip() in {'/set_botname', '/set_username'}:
        txterror = f'Ошибка: не указан новый псевдоним\\!\n`{cmd} <новый псевдоним>`'
        await add_data(msg, 'cmd response', txterror)
        await msg.answer(txterror, parse_mode='MarkdownV2')
        return

    old_bot = await get_bot_alias(msg)
    old_user = await get_user_alias(msg)

    if cmd == '/set_botname':
        bot_new = msg.text.replace(cmd, '').strip()
        user_new = old_user
        txtsuccess = f'Псевдоним бота изменён с {old_bot} на {bot_new}'
    else:  # /set_username
        user_new = msg.text.replace(cmd, '').strip()
        bot_new = old_bot
        txtsuccess = f'Ваш псевдоним изменён с {old_user} на {user_new}'

    await upd_names(msg, bot_new, user_new)
    await add_data(msg, 'cmd response', txtsuccess)
    await msg.answer(txtsuccess)


@dp.message(Command('tokens'))
async def tokens_cmd(msg: Message):
    await bot.send_chat_action(msg.chat.id, ChatAction.TYPING)
    await add_data(msg, 'cmd request', msg.text)
    tokens = await get_tokens(msg)
    txtsuccess = f'Вы потратили {tokens} токенов из {model.n_ctx()}\n'
    txtsuccess += 'Токены — это память бота: сколько информации он способен удержать в контексте'
    await add_data(msg, 'cmd response', txtsuccess)
    await msg.answer(txtsuccess)


@dp.message(Command('clear'))
async def clear_cmd(msg: Message):
    await bot.send_chat_action(msg.chat.id, ChatAction.TYPING)
    await add_data(msg, 'cmd request', msg.text)
    await clear_history(msg)
    txtsuccess = 'История диалога очищена (в памяти бота)'
    await add_data(msg, 'cmd response', txtsuccess)
    await msg.answer(txtsuccess)


@dp.message()
async def msg(msg: Message):
    try:
        await bot.send_chat_action(msg.chat.id, ChatAction.TYPING)
        prompt = msg.text
        useralias = await get_user_alias(msg)
        await add_data(msg, 'user', f'{useralias}: {prompt}\n\n')
        botalias = await get_bot_alias(msg)
        history = await get_history(msg)
        answer = model(
            f'{history}{botalias}:',
            max_tokens=MAX_TOKENS,
            echo=False,
            stop=[f'{useralias}: ', f'{botalias}: ']
        )["choices"][0]["text"]
        await add_data(msg, 'bot', f'{botalias}:{answer}\n\n')
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