
def STATE_idle():
    NextState();
    return "1"
 
def STATE_SMS_send():
    NextState();
    return "2"
 
def STATE_SMS_wait():
    NextState(STATE_idle);
    return "3"

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
    global currState,nextState

    if currState != "" and nextState != "" and currState != nextState:
        print("Transition to:"+nextState.__name__)
        currState = nextState
    
    # Execute the function
    print(currState())

    
