from .base_agent import Agent
from utils.register import register_class, registry
from collections import defaultdict
import re
import jsonlines
import json
from abc import abstractmethod
from deep_translator import GoogleTranslator

@register_class(alias="Agent.Doctor.Base")
class Doctor(Agent):
    def __init__(self, engine=None, doctor_info=None, name="A"):
        if doctor_info is None:
            self.system_message = \
                "你是一个专业且耐心的医生，下面会有患者向你咨询病情。你需要：\n" + \
                "(1) 在信息不充分的情况下，不要过早作出诊断。\n" + \
                "(2) 多次、主动地向患者提问来获取充足的信息。\n" + \
                "(3) 每次只提一个问题，尽量简短。\n" + \
                "(4) 必要时要求患者进行检查，并等待患者反馈。\n" + \
                "(5) 最后根据患者的身体状况和检查结果，给出诊断结果、对应的诊断依据和治疗方案。\n" + \
                "(6) 诊断结果需要准确到具体疾病，治疗方案中不要包含检查。"
                
            self.system_message = (
                "You are a professional and patient doctor. A patient will consult you about their condition. You need to:\n"
                "(1) Avoid making an early diagnosis if the information is insufficient. DO USE DIFFERENTIAL DIAGNOSIS, THIS IS IMPORTANT.\n"
                "(2) Ask the patient multiple questions proactively to gather enough information.\n"
                "(3) Ask only one question at a time and keep it short.\n"
                "(4) Request necessary examinations and wait for the patient's feedback to RULE OUT ITEMS ON YOUR DIFFERENTIAL DIAGNOSIS.\n"
                "(5) Provide a diagnosis based on the patient's condition and examination results, including diagnostic reasons and treatment plans.\n"
                "(6) The diagnosis should be specific to a particular disease, and the treatment plan should not include further examinations."
            )

            
        else: self.system_message = doctor_info

        self.doctor_greet = "您好，有哪里不舒服？"
        self.name = name
        self.engine = engine
        
        def default_value_factory():
            return [("system", self.system_message)]
        
        self.memories = defaultdict(default_value_factory) 

        def default_diagnosis_factory():
            return {}
        self.diagnosis = defaultdict(default_diagnosis_factory) 
        self.dialog = defaultdict(default_diagnosis_factory)
        self.dialog_summarized = defaultdict(default_diagnosis_factory)

    def get_response(self, messages):
        response = self.engine.get_response(messages)
        return response

    def get_diagnosis_by_patient_id(self, patient_id, key="ALL",translate=False):
        if key == "ALL":
            return self.diagnosis[patient_id]
        

        else:
            if translate:
                #assert key in ["症状", "辅助检查", "诊断结果", "诊断依据", "治疗方案"]
                assert key in ["Symptoms", "Auxiliary Examinations", "Diagnosis", "Diagnostic Basis", "Treatment Plan"]
                try:
                    return self.diagnosis[patient_id].get(key)
                except:
                    print(">>>>>>>>>>>>>>>>>>>>>FAILURE<<<<<<<<<<<<<<<<<<<<<<<<<<<")
                    return None
            else:            
                assert key in ["症状", "辅助检查", "诊断结果", "诊断依据", "治疗方案"]
                return self.diagnosis[patient_id].get(key)
    
    def load_diagnosis(
            self, 
            diagnosis=None, 
            patient_id=None, 
            diagnosis_filepath=None, 
            evaluation_filepath=None,
            doctor_key=None,
            translate=False
        ):
        if diagnosis is not None and patient_id is not None:
            if isinstance(diagnosis, dict):
                
                self.diagnosis[patient_id].update(diagnosis)
            else:
                self.diagnosis[patient_id].update(self.parse_diagnosis(diagnosis,translate=translate))
        elif diagnosis_filepath is not None:
            self.id = diagnosis_filepath
            if diagnosis_filepath.endswith("jsonl"):
                with jsonlines.open(diagnosis_filepath, "r") as fr:
                    for line in fr:
                        self.dialog[line["patient_id"]] = json.dumps(line["dialog_history"])
                        diagnosis = line["dialog_history"][-1]["content"]
                        self.load_diagnosis(diagnosis=diagnosis, patient_id=line["patient_id"], translate=translate)
                fr.close()
        elif evaluation_filepath is not None:
            assert doctor_key is not None
            self.id = (evaluation_filepath, doctor_key)
            if diagnosis_filepath.endswith("jsonl"):
                with jsonlines.open(evaluation_filepath, "r") as fr:
                    for line in fr:
                        assert line["doctor_name"] == doctor_key
                        diagnosis = line["doctor_diagnosis"]["diagnosis"]
                        self.diagnosis
                        self.load_diagnosis(diagnosis=diagnosis, patient_id=line["patient_id"],translate=translate)
                fr.close()
        else:
            raise Exception("Wrong!")

    def parse_diagnosis(self, diagnosis, translate=False):
        struct_diagnosis = {}
        key_array = []
        diagnosis = diagnosis + "\n#"
        if translate:
            #key_array = ["症状", "辅助检查", "诊断结果", "诊断依据", "治疗方案"]
            key_array = ["Symptoms", "Auxiliary Examinations", "Diagnosis", "Diagnostic Basis", "Treatment Plan"]
        else:
            key_array = ["症状", "辅助检查", "诊断结果", "诊断依据", "治疗方案"]
        for key in key_array:
            diagnosis_part = re.findall("\#{}\#(.*?)\n\#".format(key), diagnosis, re.S)
            if len(diagnosis_part) > 0:
                diagnosis_part = diagnosis_part[0].strip()
                diagnosis_part = re.sub(r"\#{}\#".format(key), '', diagnosis_part)
                diagnosis_part = re.sub(r"\#", '', diagnosis_part)
                diagnosis_part = diagnosis_part.strip()
                struct_diagnosis[key] = diagnosis_part
        return struct_diagnosis

    @staticmethod
    def add_parser_args(parser):
        pass

    def memorize(self, message, patient_id):
        self.memories[patient_id].append(message)

    def forget(self, patient_id=None):
        def default_value_factory():
            return [("system", self.system_message)]
        if patient_id is None:
            self.memories.pop(patient_id)
        else:
            self.memories = defaultdict(default_value_factory) 

    def speak(self, content, patient_id, patient, save_to_memory=True, update_system_prompt="", think=False, dialog=[]):
        memories = self.memories[patient_id]

        messages = [{"role": memory[0], "content": memory[1]} for memory in memories]
        

        if update_system_prompt != "":
            messages[0]["content"] = update_system_prompt

        if think:
            thoughts = self.think(content, patient_id, patient, dialog)
            messages.append({"role": "user", "content": thoughts})

        messages.append({"role": "user", "content": content})

        responese = self.get_response(messages)

        self.memorize(("user", content), patient_id)
        self.memorize(("assistant", responese), patient_id)

        return responese

    def think(self, content, patient_id, patient, dialog_history):

        from agents.prompt_templates.principles.thought import system_prompt, get_user_prompt_diagnosing_thought

        memories = self.memories[patient_id]

        messages = [{"role": memory[0], "content": memory[1]} for memory in memories]
        messages.append({"role": "user", "content": content})

        messages[0]["content"] = system_prompt

        content_concat = ""
        for convo in dialog_history:
            content_concat += convo["role"] + " " + convo["content"]

        content_concat += content

        conversation=""
        thoughts=""
        diagnosis=patient.diagnosis
        differential_diagnosis=patient.differential_diagnosis

        user_prompt = get_user_prompt_diagnosing_thought(conversation=conversation, thoughts=thoughts, diagnosis=diagnosis, differential_diagnosis=differential_diagnosis)

        messages = [{"role": memory[0], "content": memory[1]} for memory in memories]
        messages.append({"role": "user", "content": user_prompt})

        responese = self.get_response(messages)

        responese = "<Thought of the doctor>" + responese

        print(responese)

        current_diagnosis_pattern = r"## Current Diagnosis:\s(.*?)\n## Differential diagnosis:"

        # Use re.search to find the match for current diagnosis
        current_match = re.search(current_diagnosis_pattern, responese, re.DOTALL)

        # Extract the current diagnosis
        if current_match:
            current_diagnosis = current_match.group(1).strip()
            print("Current Diagnosis:", current_diagnosis)
            patient.diagnosis = current_diagnosis
        else:
            print("No match found for Current Diagnosis")

        # Define the regex pattern to extract differential diagnosis
        differential_diagnosis_pattern = r"## Differential diagnosis:\s(.*)"

        # Use re.search to find the match for differential diagnosis
        differential_match = re.search(differential_diagnosis_pattern, responese, re.DOTALL)

        # Extract the differential diagnosis
        if differential_match:
            differential_diagnosis = differential_match.group(1).strip()
            print("Differential Diagnosis:", differential_diagnosis)
            patient.differential_diagnosis = differential_diagnosis
        else:
            print("No match found for Differential Diagnosis")


        self.memorize(("user", user_prompt), patient_id)
        self.memorize(("assistant", responese), patient_id)

        return responese

    def revise_diagnosis_by_symptom_and_examination(self, patient, symptom_and_examination, translate=False):
        # load the symptom and examination from the host
        self.load_diagnosis(
            diagnosis=symptom_and_examination, 
            patient_id=patient.id
        )
        # revise the diagnosis
        # build the system message

        if translate:
            system_message = "You are a professional doctor.\n" + \
                "You are diagnosing a patient. The patient's symptoms and auxiliary examinations are as follows:\n" + \
                "#Symptoms#\n{}\n\n".format(self.get_diagnosis_by_patient_id(patient.id, key="Symptoms", translate=translate)) + \
                "#Auxiliary Examinations#\n{}\n\n".format(self.get_diagnosis_by_patient_id(patient.id, key="Auxiliary Examinations", translate=translate)) + \
                "Below you will receive a preliminary medical opinion, which includes the diagnosis, diagnostic basis, and treatment plan.\n" + \
                "(1) This medical opinion may be correct or may contain errors; it is for reference only.\n" + \
                "(2) You need to provide a more accurate and reasonable diagnosis, diagnostic basis, and treatment plan based on the patient's symptoms and auxiliary examination results.\n" + \
                "(3) Please output according to the format below.\n" + \
                "#Diagnosis#\n(1) xxx\n(2) xxx\n\n" + \
                "#Diagnostic Basis#\n(1) xxx\n(2) xxx\n\n" + \
                "#Treatment Plan#\n(1) xxx\n(2) xxx\n"
            
            content = "#Diagnosis#\n{}\n\n#Diagnostic Basis#\n{}\n\n#Treatment Plan#\n{}".format(
                self.get_diagnosis_by_patient_id(patient.id, key="Diagnosis", translate=translate), 
                self.get_diagnosis_by_patient_id(patient.id, key="Diagnostic Basis", translate=translate), 
                self.get_diagnosis_by_patient_id(patient.id, key="Treatment Plan",translate=translate)
            )

        else:

            system_message = "你是一个专业的医生。\n" + \
                "你正在为患者做诊断，患者的症状和辅助检查如下：\n" + \
                "#症状#\n{}\n\n".format(self.get_diagnosis_by_patient_id(patient.id, key="症状")) + \
                "#辅助检查#\n{}\n\n".format(self.get_diagnosis_by_patient_id(patient.id, key="辅助检查")) + \
                "下面你将收到一份初步的医疗意见，其中包含诊断结果、诊断依据和治疗方案。\n" + \
                "(1) 这份医疗意见中可能是正确的，也可能存在谬误，仅供参考。\n" + \
                "(2) 你需要根据患者的症状和辅助检查的结果，来给出更正确合理的诊断结果、诊断依据和治疗方案。\n" + \
                "(3) 请你按照下面的格式来输出。\n" + \
                "#诊断结果#\n(1) xxx\n(2) xxx\n\n" + \
                "#诊断依据#\n(1) xxx\n(2) xxx\n\n" + \
                "#治疗方案#\n(1) xxx\n(2) xxx\n"
            # build the content
            content = "#诊断结果#\n{}\n\n#诊断依据#\n{}\n\n#治疗方案#\n{}".format(
                self.get_diagnosis_by_patient_id(patient.id, key="诊断结果"), 
                self.get_diagnosis_by_patient_id(patient.id, key="诊断依据"), 
                self.get_diagnosis_by_patient_id(patient.id, key="治疗方案")
            )
        # get the revised diagnosis from the doctor
        diagnosis = self.get_response([
            {"role": "system", "content": system_message}, 
            {"role": "user", "content": content}
        ])
        # update the diagnosis of doctor for patient with "patient_id"
        self.load_diagnosis(
            diagnosis=diagnosis,
            patient_id=patient.id
        )

        return diagnosis

    def revise_diagnosis_by_others(self, patient, doctors, host_critique=None, discussion_mode="Parallel", translate=False):
        # revise_mode in ["Parallel", "Parallel_with_Critique"]
        if discussion_mode == "Parallel":
            return self.revise_diagnosis_by_others_in_parallel(patient, doctors)
        elif discussion_mode == "Parallel_with_Critique":
            return self.revise_diagnosis_by_others_in_parallel_with_critique(patient, doctors, host_critique, translate)
        else:
            raise Exception("Wrong discussion_mode: {}".format(discussion_mode))

    def revise_diagnosis_by_others_in_parallel(self, patient, doctors):
        int_to_char = {0: "A", 1: "B", 2: "C", 3: "D"}
        # load the symptom and examination from the host

        if self.translate:
            system_message = "You are a professional doctor.\n" + \
                "You are diagnosing a patient. The patient's symptoms and auxiliary examinations are as follows:\n" + \
                "#Symptoms#\n{}\n\n".format(self.get_diagnosis_by_patient_id(patient.id, key="Symptoms", translate=self.translate)) + \
                "#Auxiliary Examinations#\n{}\n\n".format(self.get_diagnosis_by_patient_id(patient.id, key="Auxiliary Examinations", translate=self.translate)) + \
                "Based on the patient's condition, you have provided a preliminary diagnosis:\n" + \
                "#Diagnosis#\n{}\n\n".format(self.get_diagnosis_by_patient_id(patient.id, key="Diagnosis", translate=self.translate)) + \
                "#Diagnostic Basis#\n{}\n\n".format(self.get_diagnosis_by_patient_id(patient.id, key="Diagnostic Basis", translate=self.translate)) + \
                "#Treatment Plan#\n{}\n\n".format(self.get_diagnosis_by_patient_id(patient.id, key="Treatment Plan", translate=self.translate)) + \
                "(1) Below you will receive diagnostic opinions from other doctors, which also include diagnosis, diagnostic basis, and treatment plan. You need to critically review and analyze these opinions.\n" + \
                "(2) If you find parts of other doctors' opinions more reasonable than yours, incorporate them into your own to improve your diagnosis.\n" + \
                "(3) If you believe your diagnosis is more scientific and reasonable than others, stick to your opinion and keep it unchanged.\n" + \
                "(4) Please output according to the format below.\n" + \
                "#Diagnosis#\n(1) xxx\n(2) xxx\n\n" + \
                "#Diagnostic Basis#\n(1) xxx\n(2) xxx\n\n" + \
                "#Treatment Plan#\n(1) xxx\n(2) xxx\n"
            

            content = ""
            for i, doctor in enumerate(doctors):
                content += "##Doctor{}##\n\n#Diagnosis#\n{}\n\n#Diagnostic Basis#\n{}\n\n#Treatment Plan#\n{}\n\n".format(
                    doctor.name,
                    doctor.get_diagnosis_by_patient_id(patient.id, key="Diagnosis", translate=self.translate), 
                    doctor.get_diagnosis_by_patient_id(patient.id, key="Diagnostic Basis", translate=self.translate), 
                    doctor.get_diagnosis_by_patient_id(patient.id, key="Treatment Plan", translate=self.translate)
                )

        else: 

            system_message = "你是一个专业的医生。\n" + \
                "你正在为患者做诊断，患者的症状和辅助检查如下：\n" + \
                "#症状#\n{}\n\n".format(self.get_diagnosis_by_patient_id(patient.id, key="症状")) + \
                "#辅助检查#\n{}\n\n".format(self.get_diagnosis_by_patient_id(patient.id, key="辅助检查")) + \
                "针对患者的病情，你给出了初步的诊断意见：\n" + \
                "#诊断结果#\n{}\n\n".format(self.get_diagnosis_by_patient_id(patient.id, key="诊断结果")) + \
                "#诊断依据#\n{}\n\n".format(self.get_diagnosis_by_patient_id(patient.id, key="诊断依据")) + \
                "#治疗方案#\n{}\n\n".format(self.get_diagnosis_by_patient_id(patient.id, key="治疗方案")) + \
                "(1) 下面你将收到来自其他医生的诊断意见，其中也包含诊断结果、诊断依据和治疗方案。你需要批判性地梳理并分析其他医生的诊断意见。\n" + \
                "(2) 如果你发现其他医生给出的诊断意见有比你的更合理的部分，请吸纳进你的诊断意见中进行改进。\n" + \
                "(3) 如果你认为你的诊断意见相对于其他医生的更科学合理，请坚持自己的意见保持不变。\n" + \
                "(4) 请你按照下面的格式来输出。\n" + \
                "#诊断结果#\n(1) xxx\n(2) xxx\n\n" + \
                "#诊断依据#\n(1) xxx\n(2) xxx\n\n" + \
                "#治疗方案#\n(1) xxx\n(2) xxx\n"
            # build the content
            content = ""
            for i, doctor in enumerate(doctors):
                content += "##医生{}##\n\n#诊断结果#\n{}\n\n#诊断依据#\n{}\n\n#治疗方案#\n{}\n\n".format(
                    doctor.name,
                    doctor.get_diagnosis_by_patient_id(patient.id, key="诊断结果"), 
                    doctor.get_diagnosis_by_patient_id(patient.id, key="诊断依据"), 
                    doctor.get_diagnosis_by_patient_id(patient.id, key="治疗方案")
                )
        responese = self.get_response([
            {"role": "system", "content": system_message}, 
            {"role": "user", "content": content}
        ])
        self.load_diagnosis(
            diagnosis=responese,
            patient_id=patient.id
        )

        return responese

    def revise_diagnosis_by_others_in_parallel_with_critique(self, patient, doctors, host_critique=None, translate=False):
        # int_to_char = {0: "A", 1: "B", 2: "C", 3: "D"}
        # load the symptom and examination from the host

        if translate:
            system_message = "You are a professional doctor {}.\n".format(self.name) + \
                "You are diagnosing a patient. The patient's symptoms and auxiliary examinations are as follows:\n" + \
                "#Symptoms#\n{}\n\n".format(self.get_diagnosis_by_patient_id(patient.id, key="Symptoms", translate=translate)) + \
                "#Auxiliary Examinations#\n{}\n\n".format(self.get_diagnosis_by_patient_id(patient.id, key="Auxiliary Examinations", translate=translate)) + \
                "Based on the patient's condition, you have provided a preliminary diagnosis:\n" + \
                "#Diagnosis#\n{}\n\n".format(self.get_diagnosis_by_patient_id(patient.id, key="Diagnosis", translate=translate)) + \
                "#Diagnostic Basis#\n{}\n\n".format(self.get_diagnosis_by_patient_id(patient.id, key="Diagnostic Basis", translate=translate)) + \
                "#Treatment Plan#\n{}\n\n".format(self.get_diagnosis_by_patient_id(patient.id, key="Treatment Plan", translate=translate)) + \
                "(1) Below you will receive diagnostic opinions from other doctors, which also include diagnosis, diagnostic basis, and treatment plan. You need to critically review and analyze these opinions.\n" + \
                "(2) During this process, please pay attention to the controversial points raised by the attending physician.\n" + \
                "(3) If you find parts of other doctors' opinions more reasonable than yours, incorporate them into your own to improve your diagnosis.\n" + \
                "(4) If you believe your diagnosis is more scientific and reasonable than others, stick to your opinion and keep it unchanged.\n" + \
                "(5) Please output according to the format below.\n" + \
                "#Diagnosis#\n(1) xxx\n(2) xxx\n\n" + \
                "#Diagnostic Basis#\n(1) xxx\n(2) xxx\n\n" + \
                "#Treatment Plan#\n(1) xxx\n(2) xxx\n"
            
            content = ""
            for i, doctor in enumerate(doctors):
                content += "##Doctor{}##\n\n#Diagnosis#\n{}\n\n#Diagnostic Basis#\n{}\n\n#Treatment Plan#\n{}\n\n#Medical transcript of consultation#{}\n\n".format(
                    doctor.name,
                    doctor.get_diagnosis_by_patient_id(patient.id, key="Diagnosis", translate=translate), 
                    doctor.get_diagnosis_by_patient_id(patient.id, key="Diagnostic Basis", translate=translate), 
                    doctor.get_diagnosis_by_patient_id(patient.id, key="Treatment Plan", translate=translate),
                    doctor.dialog_summarized[patient.id]
                    )

            content += "##Chief Doctor##\n{}".format(host_critique)

        else:
            system_message = "你是一个专业的医生{}。\n".format(self.name) + \
                "你正在为患者做诊断，患者的症状和辅助检查如下：\n" + \
                "#症状#\n{}\n\n".format(self.get_diagnosis_by_patient_id(patient.id, key="症状")) + \
                "#辅助检查#\n{}\n\n".format(self.get_diagnosis_by_patient_id(patient.id, key="辅助检查")) + \
                "针对患者的病情，你给出了初步的诊断意见：\n" + \
                "#诊断结果#\n{}\n\n".format(self.get_diagnosis_by_patient_id(patient.id, key="诊断结果")) + \
                "#诊断依据#\n{}\n\n".format(self.get_diagnosis_by_patient_id(patient.id, key="诊断依据")) + \
                "#治疗方案#\n{}\n\n".format(self.get_diagnosis_by_patient_id(patient.id, key="治疗方案")) + \
                "(1) 下面你将收到来自其他医生的诊断意见，其中也包含诊断结果、诊断依据和治疗方案。你需要批判性地梳理并分析其他医生的诊断意见。\n" + \
                "(2) 在这个过程中，请你注意主治医生给出的争议点。\n" + \
                "(3) 如果你发现其他医生给出的诊断意见有比你的更合理的部分，请吸纳进你的诊断意见中进行改进。\n" + \
                "(4) 如果你认为你的诊断意见相对于其他医生的更科学合理，请坚持自己的意见保持不变。\n" + \
                "(5) 请你按照下面的格式来输出。\n" + \
                "#诊断结果#\n(1) xxx\n(2) xxx\n\n" + \
                "#诊断依据#\n(1) xxx\n(2) xxx\n\n" + \
                "#治疗方案#\n(1) xxx\n(2) xxx\n"
            # build the content
            content = ""
            for i, doctor in enumerate(doctors):
                content += "##医生{}##\n\n#诊断结果#\n{}\n\n#诊断依据#\n{}\n\n#治疗方案#\n{}\n\n".format(
                    doctor.name,
                    doctor.get_diagnosis_by_patient_id(patient.id, key="诊断结果"), 
                    doctor.get_diagnosis_by_patient_id(patient.id, key="诊断依据"), 
                    doctor.get_diagnosis_by_patient_id(patient.id, key="治疗方案")
                )
            content += "##主任医生##\n{}".format(host_critique)

        # print("doctor: {}".format(self.name))
        # print(content)
        # print("-"*100)
        responese = self.get_response([
            {"role": "system", "content": system_message}, 
            {"role": "user", "content": content}
        ])
        self.load_diagnosis(
            diagnosis=responese,
            patient_id=patient.id
        )

        return responese

#################################################
@register_class(alias="Agent.Doctor.GPT")
class GPTDoctor(Doctor):
    def __init__(self, args=None, doctor_info=None, name="A"):
        engine = registry.get_class("Engine.LiteLLM")(
            openai_api_key=args.doctor_openai_api_key, 
            openai_api_base=args.doctor_openai_api_base,
            openai_model_name=args.doctor_openai_model_name, 
            temperature=args.doctor_temperature, 
            max_tokens=args.doctor_max_tokens,
            top_p=args.doctor_top_p,
            frequency_penalty=args.doctor_frequency_penalty,
            presence_penalty=args.doctor_presence_penalty
        )


        # elf.engine = build_engine(engine_name=model)
        # print(self.memories[0][1])

        

        super(GPTDoctor, self).__init__(engine, doctor_info, name=name)

        self.translate = args.translate
        self.thinking = args.thinking

        if args.approach == "p26":
            translator = GoogleTranslator(source='zh-CN', target='en')
            from agents.prompt_templates.principles.doctor_prompts import system_prompt_base, system_prompt_base_2 
            self.system_message = system_prompt_base_2
            self.doctor_greet = translator.translate(self.doctor_greet) 


        elif args.translate:
            translator = GoogleTranslator(source='zh-CN', target='en')
            self.system_message = translator.translate(self.system_message)
            self.doctor_greet = translator.translate(self.doctor_greet)            



           

    @staticmethod
    def add_parser_args(parser):
        parser.add_argument('--doctor_openai_api_key', type=str, help='API key for OpenAI')
        parser.add_argument('--doctor_openai_api_base', type=str, help='API base for OpenAI')
        parser.add_argument('--doctor_openai_model_name', type=str, help='API model name for OpenAI')
        parser.add_argument('--doctor_temperature', type=float, default=0.0, help='temperature')
        parser.add_argument('--doctor_max_tokens', type=int, default=2048, help='max tokens')
        parser.add_argument('--doctor_top_p', type=float, default=1, help='top p')
        parser.add_argument('--doctor_frequency_penalty', type=float, default=0, help='frequency penalty')
        parser.add_argument('--doctor_presence_penalty', type=float, default=0, help='presence penalty')                

    def get_response(self, messages):
        response = self.engine.get_response(messages)
        return response

    # def speak(self, content, patient_id, save_to_memory=True):
    #     memories = self.memories[patient_id]

    #     messages = [{"role": memory[0], "content": memory[1]} for memory in memories]
    #     messages.append({"role": "user", "content": content})

    #     response = self.get_response(messages)

    #     self.memorize(("user", content), patient_id)
    #     self.memorize(("assistant", response), patient_id)

    #     return response

@register_class(alias="Agent.Doctor.LiteLLM")
class LiteLLMDoctor(Doctor):
    def __init__(self, args=None, doctor_info=None, name="A"):
        engine = registry.get_class("Engine.LiteLLM")(
            openai_api_key=args.doctor_openai_api_key, 
            openai_api_base=args.doctor_openai_api_base,
            openai_model_name=args.doctor_openai_model_name, 
            temperature=args.doctor_temperature, 
            max_tokens=args.doctor_max_tokens,
            top_p=args.doctor_top_p,
            frequency_penalty=args.doctor_frequency_penalty,
            presence_penalty=args.doctor_presence_penalty
        )


        super(LiteLLMDoctor, self).__init__(engine, doctor_info, name=name)
        # elf.engine = build_engine(engine_name=model)
        # print(self.memories[0][1])

    @staticmethod
    def add_parser_args(parser):
        parser.add_argument('--doctor_openai_api_key', type=str, help='API key for OpenAI')
        parser.add_argument('--doctor_openai_api_base', type=str, help='API base for OpenAI')
        parser.add_argument('--doctor_openai_model_name', type=str, help='API model name for OpenAI')
        parser.add_argument('--doctor_temperature', type=float, default=0.0, help='temperature')
        parser.add_argument('--doctor_max_tokens', type=int, default=2048, help='max tokens')
        parser.add_argument('--doctor_top_p', type=float, default=1, help='top p')
        parser.add_argument('--doctor_frequency_penalty', type=float, default=0, help='frequency penalty')
        parser.add_argument('--doctor_presence_penalty', type=float, default=0, help='presence penalty')                

    def get_response(self, messages):
        response = self.engine.get_response(messages)
        return response

    def speak(self, content, patient_id, save_to_memory=True):
        memories = self.memories[patient_id]

        messages = [{"role": memory[0], "content": memory[1]} for memory in memories]
        messages.append({"role": "user", "content": content})

        response = self.get_response(messages)

        self.memorize(("user", content), patient_id)
        self.memorize(("assistant", response), patient_id)

        return response


@register_class(alias="Agent.Doctor.ChatGLM")
class ChatGLMDoctor(Doctor):
    def __init__(self, args=None, doctor_info=None, name="A"):
        engine = registry.get_class("Engine.ChatGLM")(
            chatglm_api_key=args.doctor_chatglm_api_key, 
            model_name=args.doctor_chatglm_model_name, 
            temperature=args.doctor_temperature, 
            top_p=args.doctor_top_p, 
            incremental=args.doctor_incremental,
        )
        super(ChatGLMDoctor, self).__init__(engine, doctor_info, name=name)

        def default_value_factory():
            return [("assistant", self.system_message)]
        self.memories = defaultdict(default_value_factory) 

    @staticmethod
    def add_parser_args(parser):
        parser.add_argument("--doctor_chatglm_api_key", type=str)
        parser.add_argument("--doctor_chatglm_model_name", type=str, default="chatglm_pro")
        parser.add_argument("--doctor_temperature", type=float, default=0.5)
        parser.add_argument("--doctor_top_p", type=float, default=0.9)
        parser.add_argument("--doctor_incremental", type=bool, default=True)

    def forget(self, patient_id=None):
        def default_value_factory():
            return [("assistant", self.system_message)]
        if patient_id is None:
            self.memories.pop(patient_id)
        else:
            self.memories = defaultdict(default_value_factory) 


@register_class(alias="Agent.Doctor.Minimax")
class MinimaxDoctor(Doctor):
    def __init__(self, args=None, doctor_info=None, name="A"):
        engine = registry.get_class("Engine.MiniMax")(
            minimax_api_key=args.doctor_minimax_api_key, 
            minimax_group_id=args.doctor_minimax_group_id, 
            minimax_model_name=args.doctor_minimax_model_name, 
            tokens_to_generate=args.doctor_tokens_to_generate,
            temperature=args.doctor_temperature, 
            top_p=args.doctor_top_p, 
            stream=args.doctor_stream,
        )

        super(MinimaxDoctor, self).__init__(engine, doctor_info, name=name)

        def default_value_factory():
            return []
        self.memories = defaultdict(default_value_factory) 

        self.bot_setting = [{
            "bot_name": "医生",
            "content": self.system_message
        }]

    @staticmethod
    def add_parser_args(parser):
        parser.add_argument("--doctor_minimax_group_id", type=str)
        parser.add_argument("--doctor_minimax_api_key", type=str)
        parser.add_argument("--doctor_minimax_model_name", type=str, default="abab5.5-chat")
        parser.add_argument("--doctor_tokens_to_generate", type=int, default=1024)
        parser.add_argument("--doctor_temperature", type=float, default=0.5)
        parser.add_argument("--doctor_top_p", type=float, default=1.0)
        parser.add_argument("--doctor_stream", type=bool, default=False)

    def forget(self, patient_id=None):
        def default_value_factory():
            return []
        if patient_id is None:
            self.memories.pop(patient_id)
        else:
            self.memories = defaultdict(default_value_factory) 

    @staticmethod
    def translate_role_to_sender_type(role):
        if role == "user":
            return "USER"
        elif role == "assistant":
            return "BOT"
        else:
            raise Exception("Unknown role: {}".format(role))
    
    @staticmethod
    def translate_role_to_sender_name(role):
        if role == "user":
            return "患者"
        elif role == "assistant":
            return "医生"
        else:
            raise Exception("Unknown role: {}".format(role))
        
    def speak(self, content, patient_id, save_to_memory=True):
        memories = self.memories[patient_id]
        messages = []
        for memory in memories:
            sender_type = self.translate_role_to_sender_type(memory[0])
            sender_name = self.translate_role_to_sender_name(memory[0])
            messages.append({"sender_type": sender_type, "sender_name": sender_name, "text": memory[1]})
        messages.append({"sender_type": "USER", "sender_name": "患者",  "text": content})

        responese = self.engine.get_response(messages, self.bot_setting)

        self.memorize(("user", content), patient_id)
        self.memorize(("assistant", responese), patient_id)

        return responese


@register_class(alias="Agent.Doctor.WenXin")
class WenXinDoctor(Doctor):
    def __init__(self, args=None, doctor_info=None, name="A"):
        engine = registry.get_class("Engine.WenXin")(
            wenxin_api_key=args.doctor_wenxin_api_key, 
            wenxin_sercet_key=args.doctor_wenxin_sercet_key,
            temperature=args.doctor_temperature, 
            top_p=args.doctor_top_p,
            penalty_score=args.doctor_penalty_score,
        )
        super(WenXinDoctor, self).__init__(engine, doctor_info, name=name)

        def default_value_factory():
            return []
        self.memories = defaultdict(default_value_factory) 
        # self.memories = []

    @staticmethod
    def add_parser_args(parser):
        parser.add_argument("--doctor_wenxin_api_key", type=str)
        parser.add_argument("--doctor_wenxin_sercet_key", type=str)
        parser.add_argument("--doctor_temperature", type=float, default=0.95)
        parser.add_argument("--doctor_top_p", type=float, default=0.8)
        parser.add_argument("--doctor_penalty_score", type=float, default=1.0)

    def forget(self, patient_id=None):
        def default_value_factory():
            return []
        if patient_id is None:
            self.memories = defaultdict(default_value_factory) 
        else:
            self.memories.pop(patient_id)
        
    def get_response(self, messages):
        if messages[0]["role"] == "system":
            system_message = messages.pop(0)["content"]
        else: system_message = self.system_message
        if messages[0]["role"] == "assistant":
            messages.pop(0)
        response = self.engine.get_response(messages, system=system_message)
        return response

    def speak(self, content, patient_id, save_to_memory=True):
        memories = self.memories[patient_id]
        # if memories[0][0] == "assistant":
        #     memories.pop(0)
        messages = [{"role": memory[0], "content": memory[1]} for memory in memories]
        messages.append({"role": "user", "content": content})
        responese = self.engine.get_response(messages, system=self.system_message)

        self.memorize(("user", content), patient_id)
        self.memorize(("assistant", responese), patient_id)
        return responese


@register_class(alias="Agent.Doctor.Qwen")
class QwenDoctor(Doctor):
    def __init__(self, args=None, doctor_info=None, name="A"):
        engine = registry.get_class("Engine.Qwen")(
            api_key=args.doctor_qwen_api_key, 
            model_name=args.doctor_qwen_model_name, 
            seed=1,
        )
        super(QwenDoctor, self).__init__(engine, doctor_info, name=name)

    @staticmethod
    def add_parser_args(parser):
        parser.add_argument("--doctor_qwen_api_key", type=str)
        parser.add_argument(
            "--doctor_qwen_model_name", type=str, 
            choices=["qwen-max", "qwen-max-1201", "qwen-plus-gamma", "qwen-plus", "qwen-turbo", "baichuan2-7b-chat-v1", "baichuan2-13b-chat-v1"], default="qwen-max")
        parser.add_argument("--doctor_seed", type=int, default=1)
    
    def speak(self, content, patient_id, save_to_memory=True):
        memories = self.memories[patient_id]

        messages = [{"role": memory[0], "content": memory[1]} for memory in memories]
        messages.append({"role": "user", "content": content})
        if messages[1].get("role") == "assistant":
            messages.pop(1)
        responese = self.engine.get_response(messages)
        
        self.memorize(("user", content), patient_id)
        self.memorize(("assistant", responese), patient_id)
        return responese


@register_class(alias="Agent.Doctor.HuatuoGPT")
class HuatuoGPTDoctor(Doctor):
    def __init__(self, args=None, doctor_info=None):
        engine = registry.get_class("Engine.HuatuoGPT")(
            model_name_or_path=args.doctor_huatuogpt_model_name_or_path, 
        )
        super(HuatuoGPTDoctor, self).__init__(engine, doctor_info)

    @staticmethod
    def add_parser_args(parser):
        parser.add_argument("--doctor_huatuogpt_model_name_or_path", type=str)
    
    def speak(self, content, patient_id, save_to_memory=True):
        memories = self.memories[patient_id]

        messages = [{"role": memory[0], "content": memory[1]} for memory in memories]
        messages.append({"role": "user", "content": content})
        # if messages[1].get("role") == "assistant":
        #     messages.pop(1)
        responese = self.engine.get_response(messages)
        
        self.memorize(("user", content), patient_id)
        self.memorize(("assistant", responese), patient_id)
        return responese


@register_class(alias="Agent.Doctor.HF")
class HFDoctor(Doctor):
    def __init__(self, args=None, doctor_info=None):
        engine = registry.get_class("Engine.HF")(
            model_name_or_path=args.doctor_hf_model_name_or_path, 
        )
        super(HFDoctor, self).__init__(engine, doctor_info)

    @staticmethod
    def add_parser_args(parser):
        parser.add_argument("--doctor_hf_model_name_or_path", type=str)
    
    def speak(self, content, patient_id, save_to_memory=True):
        memories = self.memories[patient_id]

        messages = [{"role": memory[0], "content": memory[1]} for memory in memories]
        messages.append({"role": "user", "content": content})
        # if messages[1].get("role") == "assistant":
        #     messages.pop(1)
        responese = self.engine.get_response(messages)
        
        self.memorize(("user", content), patient_id)
        self.memorize(("assistant", responese), patient_id)
        return responese