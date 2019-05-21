import discord

import asyncio
import config

from datetime import datetime
from pathlib  import Path
from random   import choice

client = discord.Client()

START_TIME = datetime.now()

IMG_SAVE_PATH       = Path(config.get('save_path'))
SUPPORTED_FILETYPES =  set(config.get('supported_filetypes'))

LAST_SAVED_FILE = None
IS_TRAINING     = False

def random_filename(name):
    time = str(datetime.now()).replace(':', '_')
    return f'{time}_{name}'

async def status(msg=None):
    if not msg:
        msg = choice(config.get('idle_status_options'))
    await client.change_presence(activity=discord.Game(name=msg))

async def handle_help(channel, msg, attachments):
    msgs = []

    start_command_character = config.get('start_command_character')
    for command, command_info in COMMANDS.items():
        command_info = command_info['info'].format(**config.CONFIG)
        msgs.append(f'{start_command_character}{command} - {command_info}')

    await channel.send('\n'.join(msgs))

async def handle_predict(channel, msg, attachments):
    if not attachments:
        await channel.send(f'Invalid use of !predict. Usage: !predict <attachment> (No attachment given)')
        return

    await status(msg='predicting...')

    attach = attachments[0]

    save_path = IMG_SAVE_PATH / 'predict'

    uploaded_filename = attach.filename

    if uploaded_filename[uploaded_filename.rindex('.'):].lower() not in SUPPORTED_FILETYPES:
        supported = ', '.join(SUPPORTED_FILETYPES)
        await channel.send(f'Invalid use of !predict. Filetype must be one of ({supported})')
        return

    fname = save_path / random_filename(uploaded_filename)
    await attach.save(fname)
    
    cmd = f'python learner.py --img_path "{fname}"'
    stdout, stderr = await run_cmd(cmd)

    if stdout:
        await channel.send(f'{stdout.decode()}')
    if stderr:
        await channel.send(f'[stderr]\n{stderr.decode()}')


async def handle_add(channel, msg, attachments):
    global LAST_SAVED_FILE

    await status(msg='Adding image...')

    if not attachments:
        await channel.send(f'Invalid use of !add. Usage: !add <class> <attachment> (No attachment given)')
        return

    attach = attachments[0]

    try:
        img_class = msg[0]
    except:
        await channel.send(f'Invalid use of !add. Usage: !add <class> <attachment> (No class given)')
        return

    class_path = IMG_SAVE_PATH / 'train' / img_class

    class_path.mkdir(exist_ok=True)

    uploaded_filename = attach.filename

    if uploaded_filename[uploaded_filename.rindex('.'):] not in SUPPORTED_FILETYPES:
        supported = ', '.join(SUPPORTED_FILETYPES)
        await channel.send(f'Invalid use of !add. Filetype must be one of ({supported})')
        return

    

    fname = class_path / random_filename(uploaded_filename)
    await attach.save(fname)

    LAST_SAVED_FILE = fname

async def handle_undo(channel, msg, attachments):
    global LAST_SAVED_FILE

    if LAST_SAVED_FILE:
        LAST_SAVED_FILE.unlink()
        await channel.send(f'Complete!')
        LAST_SAVED_FILE = None
    else:
        await channel.send(f'Nothing to undo...')


async def handle_ls(channel, msg, attachments):

    msg = []
    for directory in (IMG_SAVE_PATH / 'train').iterdir():
        num_items = len(list(directory.glob('*')))
        if num_items and directory.parts[-1] != 'models':
            directory = str(directory)
            directory = directory[directory.rfind('/')+1:]

            img_txt = 'image' if num_items == 1 else 'images'
            msg.append(f'{directory} - {num_items} {img_txt}')

    if msg:
        msg = '\n'.join(msg)
    else:
        msg = 'No items yet!'

    await channel.send(msg)

async def handle_train(channel, msg, attachments):
    await status('training...')

    global IS_TRAINING

    if IS_TRAINING:
        await channel.send('We are already training! Please wait until training has completed')
        return

    IS_TRAINING = True

    cmd = 'python learner.py --train'
    stdout, stderr = await run_cmd(cmd)

    if stdout:
        await channel.send(f'{stdout.decode()}')
    if stderr:
        await channel.send(f'[stderr]\n{stderr.decode()}')

    IS_TRAINING = False

async def handle_debug(channel, msg, attachments):
    msgs = []

    msgs.append(f'Uptime: {str(datetime.now() - START_TIME)}')
    
    stdout, stderr = await run_cmd('cat /proc/meminfo | grep MemAvailable')

    for line in stdout.decode('utf-8').split('\n'):
        msgs.append(line)

    stdout, stderr = await run_cmd('nvidia-smi')

    for line in stdout.decode('utf-8').split('\n'):
        msgs.append(line)

    msg = '\n'.join(msgs)
    await channel.send(msg)


async def run_cmd(cmd):
    proc = await asyncio.create_subprocess_shell(cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)

    stdout, stderr = await proc.communicate()

    return stdout, stderr


COMMANDS = {
    'help'    : dict(f=handle_help,    info='You are looking at it'),
    'add'     : dict(f=handle_add,     info='<class> <attachment> - Add an image for training'),
    'undo'    : dict(f=handle_undo,    info='Undo the previous add'),
    'ls'      : dict(f=handle_ls,      info='View the current classes and the number of images per class'),
    'train'   : dict(f=handle_train,   info='Train the model using the added images'),
    'predict' : dict(f=handle_predict, info='<attachment> - Predict the class of <attachment> using the last trained model. You may omit {start_command_character}predict for this command.'),
    'debug'   : dict(f=handle_debug,   info='sends debug information')
}

@client.event
async def on_ready():
    print("The bot is ready!")
    await status()

@client.event
async def on_message(message):
    if message.author == client.user: # ignore our own messages
        return

    has_attachment = bool(message.attachments)

    channel = message.channel

    message_not_in_allowed_channel = channel.id not in config.get('allowed_channels')
    message_not_command = not message.content.startswith(config.get('start_command_character')) and not has_attachment

    if message_not_in_allowed_channel or message_not_command:
        return

    msg = message.content[1:].lower() # get rid of the {start_command_character}

    if not msg:
        msg = 'predict'

    command, *args = msg.split()

    handler = COMMANDS.get(command)

    if handler:
        handler_function = handler['f']

        await handler_function(channel, args, message.attachments)

    await status()

if __name__ == '__main__':
    print(discord.__version__)
    print(config.get('bot_token'))
    client.run(config.get('bot_token'))