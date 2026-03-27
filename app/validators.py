def validate_phone(phone):

    return phone.isdigit() and len(phone)>=10


def validate_age(age):

    try:
        age=int(age)
        return age>0 and age<120
    except:
        return False