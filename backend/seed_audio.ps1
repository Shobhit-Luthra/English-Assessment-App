Add-Type -AssemblyName System.Speech
$dir = "C:\Users\luthr\OneDrive\Documents\Projects\English Assesment System\backend\seed_audio"
New-Item -ItemType Directory -Force -Path $dir | Out-Null

function New-Speech($ssml, $outPath) {
    $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
    $synth.SelectVoice("Microsoft Zira Desktop")
    $synth.SetOutputToWaveFile($outPath)
    $synth.SpeakSsml($ssml)
    $synth.Dispose()
}
$ns = 'xmlns="http://www.w3.org/2001/10/synthesis"'

# --- Strong candidate: exact reference, fluent S2 ---
New-Speech @"
<speak version="1.0" $ns xml:lang="en-US"><prosody rate="+10%">
Thank you for calling our support line. I understand how frustrating a delayed delivery can be, and I want to make this right for you. Let me look into your order right now and find the fastest way to get it to you.
</prosody></speak>
"@ "$dir\strong_s1.wav"

New-Speech @"
<speak version="1.0" $ns xml:lang="en-US"><prosody rate="+25%">
First, I would listen carefully to the customer without interrupting them, because they need to feel heard. Then I would apologize sincerely for the inconvenience and confirm the details of their order. Next, I would explain the two options available, either a replacement or a full refund, and let them choose. Finally, I would follow up by email to confirm the resolution and thank them for their patience.
</prosody></speak>
"@ "$dir\strong_s2.wav"

# --- Above-average: minor misreading on S1, moderate S2 ---
New-Speech @"
<speak version="1.0" $ns xml:lang="en-US">
Thank you for calling our support team. I understand how frustrating a late delivery can be, and I want to fix this for you. Let me check your order now and find a quick way to get it to you.
</speak>
"@ "$dir\above_s1.wav"

New-Speech @"
<speak version="1.0" $ns xml:lang="en-US">
First, I would listen to the customer. <break time="400ms"/>
Then I would apologize for the inconvenience. <break time="400ms"/>
Next, I would confirm the order details. <break time="500ms"/>
I would explain the replacement or refund options. <break time="400ms"/>
Finally, I would follow up by email to confirm everything. <break time="400ms"/>
</speak>
"@ "$dir\above_s2.wav"

# --- Below-average: several words dropped on S1, halting-ish S2 ---
New-Speech @"
<speak version="1.0" $ns xml:lang="en-US"><prosody rate="-15%">
Thank you calling support line. I understand delivery can be, and I want make this right. Let me look order and find way to get it.
</prosody></speak>
"@ "$dir\below_s1.wav"

New-Speech @"
<speak version="1.0" $ns xml:lang="en-US"><prosody rate="-20%">
So, um <break time="700ms"/> first I would <break time="600ms"/> listen to the customer <break time="800ms"/>
um <break time="600ms"/> then, uh <break time="700ms"/> I would apologize <break time="800ms"/>
um <break time="600ms"/> and then <break time="700ms"/> maybe offer something <break time="800ms"/>
</prosody></speak>
"@ "$dir\below_s2.wav"

# --- Weak: garbled S1, very halting short S2 ---
New-Speech @"
<speak version="1.0" $ns xml:lang="en-US"><prosody rate="-30%">
Thank calling. Understand delivery. Want right. Look order.
</prosody></speak>
"@ "$dir\weak_s1.wav"

New-Speech @"
<speak version="1.0" $ns xml:lang="en-US"><prosody rate="-35%">
Um <break time="1000ms"/> I don't know <break time="1200ms"/> maybe <break time="1000ms"/> say sorry <break time="1200ms"/> um <break time="1000ms"/>
</prosody></speak>
"@ "$dir\weak_s2.wav"

Get-ChildItem $dir | Select-Object Name, Length
