import json
from deep_translator import GoogleTranslator
import jsonlines

def translate_json_obj(json_obj, translator):
    translated_obj = {}
    for key, value in json_obj.items():
        # translated_key = translator.translate(key)
        translated_key = key
        if isinstance(value, str):
            try:
                translated_value = translator.translate(value)
            except Exception as e:
                print(e, value)
        elif isinstance(value, dict):
            translated_value = translate_json_obj(value, translator)  # Recursively translate nested dictionaries
        elif isinstance(value, list):
            translated_value = [translate_json_obj(item, translator) if isinstance(item, dict) else translator.translate(item) if isinstance(item, str) else item for item in value]
        else:
            translated_value = value  # Leave non-string values as they are

        translated_obj[translated_key] = translated_value


    return translated_obj

def translate_json(json_data, translator):

    if isinstance(json_data, list):
        return_list = []
        i = 0;
        for item in json_data:
            if isinstance(item, dict):
                translated_item = translate_json_obj(item, translator)
            elif isinstance(item, str):
                translated_item = translator.translate(item) 
            else: 
                translated_item = item


            return_list.append(translated_item)    
            
            output_file = 'translated_json.json'
            with jsonlines.open(output_file, "a") as writer:
                writer.write(translated_item)
            writer.close()

            print(i)
            i += 1
            # with open(output_file, 'a', encoding='utf-8') as f:
            #     json.dump(translated_item, f, ensure_ascii=False, indent=2)

        return return_list              

        return [translate_json_obj(item, translator) if isinstance(item, dict) else translator.translate(item) if isinstance(item, str) else item for item in json_data]
    elif isinstance(json_data, dict):
        return translate_json_obj(json_data, translator)
    else:
        raise ValueError("Unsupported JSON structure")

# Load JSON object from a file
input_file = 'src\\data\\patients.json'
with open(input_file, 'r', encoding='utf-8') as f:
    chinese_json = json.load(f)

# Create a translator instance
translator = GoogleTranslator(source='zh-CN', target='en')

# Translate the JSON object
translated_json = translate_json(chinese_json, translator)

# Save the translated JSON object to a file
output_file = 'translated_json.json'
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(translated_json, f, ensure_ascii=False, indent=2)

print(f"Translated JSON object has been saved to '{output_file}'")
