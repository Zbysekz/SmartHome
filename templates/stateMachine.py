import time
tmrTimeout = 0

def STATE_idle():
    NextState();
 
def STATE_SMS_send():
    NextState();
 
def STATE_SMS_wait():

    if False:
        NextState(STATE_idle);

    if CheckTimeout(5):
        Log("Timeout in state:"+str(currState))
        NextState(STATE_idle)

stateList = [
    STATE_idle,
    STATE_SMS_send,
    STATE_SMS_wait
]

currState = STATE_idle
nextState = ""

def NextState(name = ""):
    global switcher,currState,nextState

    if name == "":
        idx = stateList.index(currState)
        idx = idx + 1
        nextState = stateList[idx]
    else:
        nextState = name
    
 
def Process():
    global currState,nextState,tmrTimeout

    if currState != "" and nextState != "" and currState != nextState:
        print("Transition to:"+nextState.__name__)
        currState = nextState
        tmrTimeout = time.time()
    
    # Execute the function
    currState()


def CheckTimeout(timeout):#in seconds
    global tmrTimeout

    if time.time() - tmrTimeout > timeout:
        return True
    else:
        return False
