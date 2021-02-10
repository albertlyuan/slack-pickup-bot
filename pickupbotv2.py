"""
Created on 12/21/2020

@author: Albert
"""
"""
Created on 12/4/2020

@author: Albert
"""
import slack
import os
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, request, Response
from slackeventsapi import SlackEventAdapter
import string
from datetime import datetime, timedelta, date
import inflect

p = inflect.engine()

# import pprint for debuging
# printer.pprint(item)
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

app = Flask(__name__)  # flask is named appscratch
slack_event_adapter = SlackEventAdapter(
    os.environ['SIGNING_SECRET'], '/slack/events', app)

client = slack.WebClient(token=os.environ['SLACK_TOKEN'])
BOT_ID = client.api_call("auth.test")['user_id']

survey_messages = {}
survey_results = {}
survey_key = {}
ephemeral_reg = {}


class start_text:
    START_TEXT = {
        'type': 'section',
        'text': {
            'type': 'mrkdwn',
            'text': (
                'Wanna play frisbee? \n\n'
                'React to the time that works:'
            )
        }
    }
    DIVIDER = {'type': 'divider'}

    def __init__(self, channel, user) -> object:
        self.channel = channel
        self.user = user
        self.icon_emoji = ':smiling_imp:'
        self.timestamp = ''
        self.completed = False

    def get_message(self):
        return {
            'ts': self.timestamp,
            'channel': self.channel,
            'username': 'Pickup',
            'blocks': [
                self.START_TEXT,
                self.DIVIDER,
                self._get_reaction()
            ]
        }

    def _get_reaction(self):
        text = ':two: *2pm*' + '\n' + ':three: *3pm*' + '\n' + \
               ':four: *4pm*' + '\n'

        return {'type': 'section', 'text': {'type': 'mrkdwn', 'text': text}}


def send_survey_message(channel, user, today):
    # create objects
    start = start_text(channel, user)

    # make messages
    startmessage = start.get_message()

    # post messages
    # **reformats 'channel': to channel=@id
    print("mark", startmessage)
    startresponse = client.chat_postMessage(**startmessage)
    print(startresponse)
    start.timestamp = startresponse['ts']
    start_url = client.chat_getPermalink(channel=channel,
                                         message_ts=start.timestamp)
    if today not in survey_messages:
        survey_messages[today] = {}
    survey_messages[today]['ts'] = start.timestamp
    survey_messages[today]['url'] = start_url.get('permalink')
    print(start_url)
    print('pickup ts', survey_messages)
    options_str = startmessage.get('blocks')[2].get('text').get('text')
    options_lst = options_str.split(':')
    print(options_lst)
    for option in options_lst:
        if '*' in option:
            a = option.index('*')
            b = option.rindex('*')
            temp = option[a + 1:b]

            findm = temp.index('m')
            number = temp[:findm - 1]
            word = p.number_to_words(number)
            client.reactions_add(channel=channel, timestamp=start.timestamp,
                                 name=word)
            survey_results[today][word] = []
            if today not in survey_key:
                survey_key[today] = {}
            survey_key[today][word] = temp

    print('init')
    print(survey_results)
    print(survey_key)
    print('init')


@slack_event_adapter.on('reaction_added')
def reaction(payload):
    check_today = date.today()
    event = payload.get('event', {})
    user_id = event.get('user')
    message_id = event.get('item', {}).get('ts')
    user_name = client.users_info(user=user_id).get('user').get('real_name')
    if user_id == BOT_ID or user_id == None:
        return
    if check_today not in survey_results:
        return
    if message_id not in survey_messages[check_today]['ts']:
        return
    emoji_type = event.get('reaction')
    if emoji_type not in survey_results[check_today]:
        print('emoji not there')
        print(survey_results[check_today])
        return
    survey_results[check_today][emoji_type].append(user_name)
    print(survey_results)


@slack_event_adapter.on('reaction_removed')
def remove_message(payload):
    print('removed')
    check_today = date.today()
    event = payload.get('event', {})
    user_id = event.get('user')
    message_id = event.get('item', {}).get('ts')
    user_name = client.users_info(user=user_id).get('user').get('real_name')

    if check_today not in survey_results:
        return
    if message_id not in survey_messages[check_today]['ts']:
        return
    emoji_type = event.get('reaction')
    if emoji_type not in survey_results[check_today]:
        print('emoji not there')
        print(survey_results[check_today])
        return
    survey_results[check_today][emoji_type].remove(user_name)
    print(survey_results)


def formatwinner(winner, date):
    message = ""
    for option in winner:
        persons = ",".join(option[1])
        if len(option[1]) == 1:
            message += option[0] + ": " + persons + \
                       " (" + str(len(option[1])) + " player) \n"
        else:
            message += option[0] + ": " + persons + \
                       " (" + str(len(option[1])) + " players) \n"
    message += str(survey_messages[date]['url'])
    return message


def availability(date):
    winner = [('', [])]
    #print(survey_results[date])
    for time, people in survey_results[date].items():
        remove_repeat = set(people)
        unique_people = list(remove_repeat)
        num_people = len(unique_people)
        #print("num peep", num_people)
        if num_people > len(winner[0][1]):
            time_name = survey_key[date].get(time)
            winner = [(time_name, unique_people)]
        elif num_people == len(winner[0][1]):
            time_name = survey_key[date].get(time)
            winner.append((time_name, unique_people))
    #print(winner)
    return formatwinner(winner, date)


@app.route('/pickup', methods=['POST'])
def pickup():
    check_today = date.today()
    data = request.form
    user_id = data.get('user_id')
    channel_id = data.get('channel_id')

    if check_today in survey_results:
        print("tried pickup")
        times = availability(check_today)
        client.chat_postEphemeral(channel=channel_id,
                                  user=user_id, text=times,
                                  delete_original=True)
        '''pvt_response = client.chat_postEphemeral(channel=channel_id,
                                                 user=user_id, text=times, 
                                                 replace_original=True)
        pvt_ts = pvt_response['ts']
        if user_id in ephemeral_reg:
            old_ts = ephemeral_reg.get(user_id)
            client.chat_delete(channel=channel_id, ts=old_ts)
            ephemeral_reg[user_id] = pvt_ts

        else:
            ephemeral_reg[user_id] = pvt_ts'''
        return Response(), 200
        # eventually reroute to bring up old request
    else:
        survey_results[check_today] = {}

    send_survey_message(channel_id, user_id, check_today)
    print(survey_results)
    print(survey_key)

    return Response(), 200


if __name__ == '__main__':
    app.run(debug=True, port=80)
