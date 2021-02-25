import requests
import os
import logging
import psycopg2
import datetime

from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger(__name__)

TOKEN = os.environ['API_KEY']
CHAT_ID = "349425211"

class Event:
    def __init__(self, title, url):
        self.title = title
        self.url = url
    
    def getTitle(self):
        return self.title
    
    def getUrl(self):
        return self.url


def scrape_events():
    website_link = "https://qa.datateknologerna.org/events/"
    source = requests.get(website_link)
    soup = BeautifulSoup(source.content, 'html.parser')

    events = []
    for a in soup.find_all(class_='event-coming', href=True):
        event_title = a.find_all(class_='event-title')[0].text
        event_url = "https://datateknologerna.org" + a['href']
        event = Event(event_title, event_url)
        events.append(event)
    return events


def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('Hi! Use /set to start tracking new events')


def alarm(context):
    try:
       DATABASE_URL = os.environ['DATABASE_URL']
       conn = psycopg2.connect(DATABASE_URL, sslmode='require')
       events_db = conn.cursor()
       events_db.execute('CREATE TABLE IF NOT EXISTS events (id SERIAL, event TEXT NOT NULL)')
    except:
       send_message(chat_id, 'The database could not be accessed')
        
    # crawl the jobs from website
    events = scrape_events()
    # check if there were new jobs added
    for item in events:
        job_exists = events_db.execute('SELECT event FROM events WHERE event = %s', [item.title])
        
        if len(events_db.fetchall()) != 1:
            mess_content = "🎉New DaTe event!🎉\n" + item.title + "\n" + item.url
            job = context.job
            context.bot.send_message(job.context, text=mess_content)
            events_db.execute('INSERT INTO events (event) VALUES (%s);', [item.title])
            conn.commit()
        else:
            continue
            
    # end SQL connection
    events_db.close()



def remove_job_if_exists(name, context):
    """Remove job with given name. Returns whether job was removed."""
    current_jobs = context.job_queue.get_jobs_by_name(name)
    if not current_jobs:
        return False
    for job in current_jobs:
        job.schedule_removal()
    return True


def set_timer(update: Update, context: CallbackContext) -> None:
    """Add a job to the queue."""
    chat_id = update.message.chat_id
    try:
        # args[0] should contain the time for the timer in seconds
        job_removed = remove_job_if_exists(str(chat_id), context)
        context.job_queue.run_daily(alarm, datetime.time(hour=16, minute=12, tzinfo=pytz.timezone('Europe/Helsinki')), context=chat_id, name=str(chat_id))

        text = 'Tracking DaTe events'
        if job_removed:
            text += ' Old one was removed.'
        update.message.reply_text(text)

    except (IndexError, ValueError):
        update.message.reply_text('Usage: /set <seconds>')


def unset(update: Update, context: CallbackContext) -> None:
    """Remove the job if the user changed their mind."""
    chat_id = update.message.chat_id
    job_removed = remove_job_if_exists(str(chat_id), context)
    text = 'Events tracking stopped.' if job_removed else 'You are currently not tracking events'
    update.message.reply_text(text)


def main():
    # Create the Updater and pass it your bot's token.
    updater = Updater(TOKEN)

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", start))
    dispatcher.add_handler(CommandHandler("set", set_timer))
    dispatcher.add_handler(CommandHandler("unset", unset))

    # Start the Bot
    updater.start_polling()

    # Block until you press Ctrl-C or the process receives SIGINT, SIGTERM or
    # SIGABRT. This should be used most of the time, since start_polling() is
    # non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()