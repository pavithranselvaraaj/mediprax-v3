complaints = {

"F":[
"Fever with cold",
"Fever without cold"
],

"G":[
"Giddiness"
],

"R":[
"Road Traffic Accident"
]

}

def suggest_complaint(letter):

    if not letter:
        return []

    return complaints.get(letter.upper(),[])