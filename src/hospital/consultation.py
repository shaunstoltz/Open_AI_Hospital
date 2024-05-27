import argparse
import os
import json
from typing import List
import jsonlines
from tqdm import tqdm
import time
import concurrent
import random
from utils.register import register_class, registry


@register_class(alias="Scenario.Consultation")
class Consultation:
    def __init__(self, args):
        with open(args.patient_database, 'r', encoding='utf-8') as f:
            patient_database = json.load(f)
        # patient_database = json.load(open(args.patient_database))
        self.args = args
        self.doctor = registry.get_class(args.doctor)(
            args,
        )



        
        self.patients = []

        i = 1
        for patient_profile in patient_database:
            patient = registry.get_class(args.patient)(
                args,
                patient_profile=patient_profile["profile"],
                medical_records=patient_profile["medical_record"],
                patient_id=patient_profile["id"]
            )

            self.patients.append(patient)
            if args.patientset > 0:
                if args.patientset == i:
                    break
                else:
                    i = i + 1


          
        self.reporter = registry.get_class(args.reporter)(args)

        self.medical_director_summary_query = \
            "您能分别总结一下病人的症状和辅助检查的结果，然后给出您的诊断结果、诊断依据和治疗方案吗？" + \
            "按照下面的格式给出。\n\n" + \
            "#症状#\n(1)xx\n(2)xx\n\n" + \
            "#辅助检查#\n(1)xx\n(2)xx\n\n" + \
            "#诊断结果#\nxx\n\n" + \
            "#诊断依据#\n(1)xx\n(2)xx\n\n" + \
            "#治疗方案#\n(1)xx\n(2)xx" 
        
        self.max_conversation_turn = args.max_conversation_turn
        self.delay_between_tasks = args.delay_between_tasks
        self.max_workers = args.max_workers
        self.save_path = args.save_path
        self.ff_print = args.ff_print
        self.start_time = time.strftime('%Y-%m-%d %H:%M:%S')

        self.translate = args.translate
        self.approach = args.approach
        self.pasthistory = args.pasthistory
        self.thinking = args.thinking

        if self.translate:
            self.medical_director_summary_query = \
                "Can you separately summarize the patient's symptoms and the results of auxiliary examinations, then provide your diagnosis, diagnostic basis, and treatment plan?" + \
                "Please follow the format below.\n\n" + \
                "#Symptoms#\n(1)xx\n(2)xx\n\n" + \
                "#Auxiliary Examinations#\n(1)xx\n(2)xx\n\n" + \
                "#Diagnosis#\nxx\n\n" + \
                "#Diagnostic Basis#\n(1)xx\n(2)xx\n\n" + \
                "#Treatment Plan#\n(1)xx\n(2)xx"            

    @staticmethod
    def add_parser_args(parser: argparse.ArgumentParser):
        parser.add_argument("--patient_database", default="patients.json", type=str)
        parser.add_argument("--patient", default="Agent.Patient.GPT", help="registry name of patient agent")
        parser.add_argument("--doctor", default="Agent.Doctor.GPT", help="registry name of doctor agent")
        parser.add_argument("--reporter", default="Agent.Reporter.GPT", help="registry name of reporter agent")

        parser.add_argument("--max_conversation_turn", default=10, type=int, help="max conversation turn between doctor and patient")
        parser.add_argument("--max_workers", default=4, type=int, help="max workers for parallel diagnosis")
        parser.add_argument("--delay_between_tasks", default=10, type=int, help="delay between tasks")
        parser.add_argument("--save_path", default="dialog_history.jsonl", help="save path for dialog history")
        parser.add_argument("--ff_print", default=True, action="store_true", help="print dialog history")
        parser.add_argument("--parallel", default=False, action="store_true", help="parallel diagnosis")

        parser.add_argument("--translate", default=False, type=bool, help="translate to english")
        parser.add_argument("--translated", default=False, type=bool, help="medical json already translated to english")
        parser.add_argument("--approach", default="base", type=str, help="prompting approach to take")
        parser.add_argument("--pasthistory", default=False, type=bool, help="whether to add past medical history to doctor knowledge at the start")
        parser.add_argument("--thinking", default=False, type=bool, help="whether to add thinking to the doctor before speaking")
        parser.add_argument("--patientset", default=0, type=int, help="max number of patients to diagnose]")


    def remove_processed_patients(self):
        processed_patient_ids = {}
        if os.path.exists(self.save_path):
            with jsonlines.open(self.save_path, "r") as f:
                for obj in f:
                    processed_patient_ids[obj["patient_id"]] = 1
            f.close()

        patient_num = len(self.patients)
        for i, patient in enumerate(self.patients[::-1]):
            if processed_patient_ids.get(patient.id) is not None:
                self.patients.pop((patient_num-(i+1)))
            
        random.shuffle(self.patients)
        print("To-be-diagnosed Patient Number: ", len(self.patients))

    def run(self):
        self.remove_processed_patients()
        st = time.time()
        for patient in tqdm(self.patients):
            self._diagnosis(patient)
            # patient.forget()
            # self.doctor.forget()
        print("duration: ", time.time() - st)

    def parallel_run(self):
        self.remove_processed_patients()

        st = time.time()
        print("Parallel Diagnosis Start")
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 使用 map 来简化提交任务和获取结果的过程
            # executor.map(self._diagnosis, self.patients)
            futures = [executor.submit(self._diagnosis, patient) for patient in self.patients]
            # 使用 tqdm 来创建一个进度条
            for _ in tqdm(concurrent.futures.as_completed(futures), total=len(self.patients)):
                pass

        print("duration: ", time.time() - st)
        
    def _diagnosis(self, patient):

        past_history = ""
        if self.pasthistory:
            from agents.prompt_templates.principles.doctor_prompts import system_prompt_with_patient_history
            past_history = system_prompt_with_patient_history(patient.medical_records["既往史"])

        dialog_history = [{"turn": 0, "role": "Doctor", "content": self.doctor.doctor_greet}]
        self.doctor.memorize(("assistant", self.doctor.doctor_greet), patient.id)
        if self.ff_print:
            print("############### Dialog ###############")
            print("--------------------------------------")
            print(dialog_history[-1]["turn"], dialog_history[-1]["role"])
            print(dialog_history[-1]["content"])

        continue_conversation = True
        turn = 0
        conversation_reseter = 0

        #for turn in range(self.max_conversation_turn):

        while continue_conversation:
            patient_response = patient.speak(dialog_history[-1]["role"], dialog_history[-1]["content"])
           
            dialog_history.append({"turn": turn+1, "role": "Patient", "content": patient_response})
            if self.ff_print:
                print("--------------------------------------")
                print(dialog_history[-1]["turn"], dialog_history[-1]["role"])
                print(dialog_history[-1]["content"])
            if "<结束>" in patient_response: 
                continue_conversation = False
                break
            if "<End>" in patient_response: 
                continue_conversation = False
                break




            speak_to, patient_response = patient.parse_role_content(patient, patient_response)

            if speak_to == "医生" or speak_to == "doctor":


                doctor_response = self.doctor.speak(patient_response, patient.id, patient, update_system_prompt=past_history, think=self.thinking, dialog=dialog_history)
                
                dialog_history.append({"turn": turn+1, "role": "Doctor", "content": doctor_response})
            elif speak_to == "检查员" or speak_to == "examiner":
                if self.approach != "base" and False:

                    reporter_response = patient.body.speak_test_results(role="test_results", save_to_memory=True, test_requested=patient_response, current_treatments="", translate=False)
                    dialog_history.append({"turn": turn+1, "role": "Test Results", "content": reporter_response})
                else:
                    reporter_response = self.reporter.speak(patient.medical_records, patient_response)
                    check_response = patient.body.speak_check_results(patient, patient_response, reporter_response)

                    dialog_history.append({"turn": turn+1, "role": "Reporter", "content": reporter_response})
                    dialog_history.append({"turn": turn+1, "role": "Body test checker", "content": check_response})
                    print("Reporter>>>>>>>>>>>>",reporter_response,"<<<<<<<<<<<<<check  ",check_response)
                    
                doctor_response = self.doctor.speak(reporter_response, patient.id, patient, update_system_prompt=past_history, think=self.thinking, dialog=dialog_history)
                dialog_history.append({"turn": turn+1, "role": "Doctor", "content": doctor_response})
            else:
                raise "Wrong!"
            if self.ff_print:
                if speak_to == "检查员" or speak_to == "examiner":
                    print("--------------------------------------")
                    print(dialog_history[-2]["turn"], dialog_history[-2]["role"])
                    print(dialog_history[-2]["content"])
                print("--------------------------------------")
                print(dialog_history[-1]["turn"], dialog_history[-1]["role"])
                print(dialog_history[-1]["content"])
            turn = turn + 1

            if turn > self.max_conversation_turn:


                continue_conversation = False

        
        
        doctor_response = self.doctor.speak(self.medical_director_summary_query, patient.id, patient, update_system_prompt=past_history, think=False, dialog=[])
        dialog_history.append({"turn": turn+1, "role": "Doctor", "content": doctor_response})
        if self.ff_print:
            print("--------------------------------------")
            print(dialog_history[-1]["turn"], dialog_history[-1]["role"])
            print(dialog_history[-1]["content"])
            # self.evaluate(patient_profile, doctor_response)

        dialog_info = {
            "patient_id": patient.id,
            "doctor": self.args.doctor,
            "doctor_engine_name": self.doctor.engine.model_name,
            "patient": self.args.patient,
            "patient_engine_name": patient.engine.model_name,
            "reporter": self.args.reporter,
            "reporter_engine_name": self.reporter.engine.model_name,
            "dialog_history": dialog_history,
            "time": self.start_time,
            "doctor_memories": self.doctor.memories[patient.id],
            "patient_memories": patient.memories
        }
        self.save_dialog_info(dialog_info)
    
    def save_dialog_info(self, dialog_info):
        with jsonlines.open(self.save_path, "a") as f:
            f.write(dialog_info)
        f.close()
