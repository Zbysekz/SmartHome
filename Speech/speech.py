#!/usr/bin/env python3

# NOTE: this example requires PyAudio because it uses the Microphone class
##import os, sys
##sys.path.append(os.path.join(os.path.dirname(__file__), "Speech"))

import speech_recognition as sr
import snowboydecoder_arecord
import snowboydecoder
import sys
import signal
import os

interrupted = False
# recognize speech using Google Cloud Speech
GOOGLE_CLOUD_SPEECH_CREDENTIALS = r"""{
  "type": "service_account",
  "project_id": "thematic-coda-203011",
  "private_key_id": "774984f52fb9e23b5ff07dc1f73c90e3d6ec00f6",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDB7ORU3+A2DvIH\ntIJqi1byJj/okDT4de2XtBNmQkiBROMInP2z5GhzZjrgVRe4pSPAYd6/BoZ0nfVo\nbiagiMDZhhfqO732Jpcgq6S7mDJIBUEmypSMpOf0JF7KpXFu2hSb3v6jC7WfXnYp\nIW0rbn/rNH/90fbDumzgQDMAGhlG4hvpgcB/wEuuBWmJ8mth9oY1yMKRpLy5jXeF\n0Gfi1IQGm3jVI5hbPS4313yVUd8bIxviMOeX7xHj2B0kpcbpyizufkVk+ObPl5G5\nEE19yKGsy+HsNpxm+MRkwir7E/Hfhp27z4HegBBWoomBlzyXrWygtPS/g8wSJ0Eu\npiSyduKtAgMBAAECggEAERoGgtOhbrL/th09mQ7DsqQb47L/8N9ZfhTj1xNGWJwO\nF37cwsYEThT4YTsv1dk+X2NiJN968QLTFwwLvQGCXEx+hGoTVQdPMZLheqev23kX\nJ0gbNJIAYJ/qeh1/9OInih1uwEsyj6Thb7wiZ/+dKU1ecjBXfihNHLOcq8ghbYYw\nhyJNODc+t9AEWPpq72bb/clGtuHlVaqGD4iVCpdLt/FTDXlD3ZZIziisj1xQA2Pl\nfNgo06qXRKCrkBwzL9SU+0HITofgoC8wXREMb7Ao1DfqY/rQe7HKnUAEwDxDN50B\ny8dPq6lfBcae7T4IMalpe7ve/qJ96GM+jdsctN+fwQKBgQD9ZukHUrhIdlkcGQYW\neMhqTEa4s7xSUsDehDZL7ioafSWlsAHVzphq7/VFo1ItMvhMedSGMNjKU+H/30Ec\naEmgJEqImgrO9aSa6IoVW111WKa67zn8mogUaPz7wUC2g6Lgt5Ldkgn0pueKLVRZ\nkAKrBlw9iIwmOfA7glTDN2VWYQKBgQDD6eBxTqyuJbkvYzPIVAFgVzar45hG/EFN\nualSL8isf+mzCl0qfjJr3j4BWPHhcrPGLwmKzbiT0+lwC4hxXViPdGRZDL5WNxvN\nMEVOOhb9oCTFXijrm7Q+uHslbPC77d/SgkWocQChibKBifKxyb0WdvYx0lS1a2Bq\n/girKk4XzQKBgBLgYaeL//JV7plrO8rcwIE6oWIM8ZBoXbm1u524ZiaHABDxpZFZ\nzHza1ziSzAJV860uvigo511bFlDLPrxxAFsPmQXIA9oa7mIjxHWG0tV0/yaZv4YT\ntONgVsgiQ0HVWILI6gXbZSZ2cHUYn1n0ol4/IQvsahRG6KBmOw43yDLBAoGAOCh4\nX8JvmVPS65SCKXB7HISjdU4+Pkrc5UzNDnQID/pyoRHddurJxUXlfDlkzH02rx6Y\nm6Mwv59FEQsdR3G8ixKQGT6f6NLPM1gc5bmdEYKwR6sgC7mMR1ZWZnn938DmIc+Z\n7BjIV4XDF4LVgMUVYLUlCU8DXSW0c7byAS6VSBkCgYEAoaxUQESk3ePl+g1kQ+Yc\nhrGeBNASB73A2qGwHuJAWxkgEIWLX4a3+4DZFDGPVoiHjW/pimFlmqbcknWHy5Zb\nA3vbHe6GeO+f+U4asqgJa8uRFFA5dm5ezJKBsbBmYL0os47M0+cEHrYgJVwQIZ9X\nXrGEj56RNPq1tEVcgVjjNGE=\n-----END PRIVATE KEY-----\n",
  "client_email": "home-automation@thematic-coda-203011.iam.gserviceaccount.com",
  "client_id": "100418880463181527334",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://accounts.google.com/o/oauth2/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/home-automation%40thematic-coda-203011.iam.gserviceaccount.com"
}
"""
    
def audioRecorderCallback(fname):
    global GOOGLE_CLOUD_SPEECH_CREDENTIALS
    print("converting audio to text")
    r = sr.Recognizer()
    with sr.AudioFile(fname) as source:
        audio = r.record(source)  # read the entire audio file
    # recognize speech using Google Speech Recognition
  # recognize speech using Google Speech Recognition
    ##try:
    ##    # for testing purposes, we're just using the default API key
    ##    # to use another API key, use `r.recognize_google(audio, key="GOOGLE_SPEECH_RECOGNITION_API_KEY")`
    ##    # instead of `r.recognize_google(audio)`
    ##    print("Google Speech Recognition thinks you said " + r.recognize_google(audio))
    ##except sr.UnknownValueError:
    ##    print("Google Speech Recognition could not understand audio")
    ##except sr.RequestError as e:
    ##    print("Could not request results from Google Speech Recognition service; {0}".format(e))

    
    retVal=-1
    try:
        text = ""
        text = r.recognize_google_cloud(audio,language="cs-CZ", credentials_json=GOOGLE_CLOUD_SPEECH_CREDENTIALS)
        #print(">> " + text)
        retVal=0
    except sr.UnknownValueError:
        print("Google Cloud Speech could not understand audio")
    except sr.RequestError as e:
        print("Could not request results from Google Cloud Speech service; {0}".format(e))

        
    print(text)
    synthesize_text(text)
    os.remove(fname)
    
def signal_handler(signal, frame):
    global interrupted
    interrupted = True


def interrupt_callback():
    global interrupted
    return interrupted

def myCallback():
    print("Poslouchám..")
    snowboydecoder.play_audio_file(snowboydecoder.DETECT_DING)
    
    
    
def synthesize_text(text):
    from gtts import gTTS
    tts = gTTS(text,lang='cs')
    tts.save('output.mp3')
    
##    """Synthesizes speech from the input string of text."""
##    from google.cloud import texttospeech
##    client = texttospeech.TextToSpeechClient()
##
##    input_text = texttospeech.types.SynthesisInput(text=text)
##
##    # Note: the voice can also be specified by name.
##    # Names of voices can be retrieved with client.list_voices().
##    voice = texttospeech.types.VoiceSelectionParams(
##        language_code='cs-CZ',
##        ssml_gender=texttospeech.enums.SsmlVoiceGender.MALE)
##
##    audio_config = texttospeech.types.AudioConfig(
##        audio_encoding=texttospeech.enums.AudioEncoding.MP3)
##
##    response = client.synthesize_speech(input_text, voice, audio_config)
##
##   # The response's audio_content is binary.
##    with open('output.mp3', 'wb') as out:
##        out.write(response.audio_content)
##        print('Audio content written to file "output.mp3"')
##    snowboydecoder.play_audio_file("output.mp3")
    from pygame import mixer # Load the required library

    mixer.init()
    mixer.music.load('output.mp3')
    mixer.music.play()
    
if __name__ == '__main__':
    
    model = "heyneo.pmdl"

    # capture SIGINT signal, e.g., Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)

    detector = snowboydecoder.HotwordDetector(model, sensitivity=0.5)
    print('Listening... Press Ctrl+C to exit')


    # main loop
    detector.start(detected_callback = myCallback,#detected_callback=snowboydecoder_arecord.play_audio_file,
                   audio_recorder_callback=audioRecorderCallback,
                   interrupt_check=interrupt_callback,
                   sleep_time=0.03)

    
    detector.terminate()