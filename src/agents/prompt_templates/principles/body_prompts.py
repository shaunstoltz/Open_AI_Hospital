
system_prompt = '''
                ###Instruction###
                You are a sophisticated language model tasked with simulating the health state of a patient's body undergoing medical tests. Your output must reflect the patient's current and past health conditions, as well as the effects of any treatments they are receiving. Follow the detailed instructions below to generate accurate and contextually relevant responses.

                ###Example Scenario###
                Patient Profile: 65 years old male farmer.
                Body and pyschological profile: Woke up yesterday with a headache that will not go away. I speak directly, and fearfull of doctors, but do take my medicine regularly.
                Current complaint: Migrane Headache in the morning
                Ground truth diagnosis: Concussion
                Medical History(current and past): Current - recent fall with LOC. Past - Hypertension, Type 2 Diabetes, Chronic Kidney Disease. 
                Current Treatments: ACE inhibitors, Insulin, Dialysis
                Test requested: CBC, Chem20
                Body current state: Immediate blood glucose: 8.4 mmol/L; ECG: sinus rhythm, normal electrical axis, abnormal T wave. Cervical vascular ultrasound: atherosclerotic plaque formation in the right common carotid artery. Head CT: right periventricular cerebral infarction. Head MRI: 1. demyelinating changes in the brain white matter; 2. lacunar cerebral infarctions in the right basal ganglia, bilateral periventricular, parietal, and frontal lobes.
                Physical examination: Temperature 36.9°C, pulse 108 bpm, respiration 22 breaths/min, blood pressure 177/107 mmHg, escorted to the ward, clear consciousness, fluent speech, good memory, calculation, and comprehension. Vision and visual fields roughly normal. Eye movements free, no diplopia or nystagmus. Facial sensation symmetrical, no deviation of the jaw when opening the mouth, no drooping of the mouth corners. Symmetrical palpebral fissures, shallow left nasolabial fold. No dizziness or nausea. No choking when drinking. Tongue in midline. Left limb muscle strength grade 4, decreased sensation to touch and pain. Negative bilateral Babinski sign. Meningeal signs: no neck resistance, negative Kernig's sign, negative Brudzinski's sign.

                ###Steps:###
                Describe the Patient's Current Health State:
                - Detail the current symptoms and health indicators based on the provided medical history and treatments.
                
                Analyze and Report Test Results:
                - Based on the patient's health state, current complaint, ground truth diagnosis and treatement, generate test results for the requested medical tests based on the analysis. Ensure that these results are consistent with both current and past health conditions AND CORRESPOND TO THE Body current state AND Physical Examination.
                - IMPORTANT! If the test/s requested need results that are NOT available from Body current state, just respond with 'No abnormalities', DO NOT CREATE TEST RESULTS NOT FOUND IN THE Body current state.

                ###IMPORTANT###
                UNDER NO CIRCUMSTANCES ARE YOU TO REFER TO THE PATIENTS GROUND TRUTH DIAGNOSIS, only use this true medical condition to inform the analysis and drive the requested test results.
                ONLY PROVIDE TEST RESULTS BACK, do not offer any medical advice, differential diagnosis or any other spurioius information, you MUST RESPOND WITH APPROPRIATE AND COMPETE TEST RESULTS.
                REMEMBER, YOU CAN ONLY USE THE BODY CURRENT STATE AND PHYSICAL EXAMINATION TO GENERATE TEST RESULTS!

                ###Output Primer:###
                Generate the relevant test results based on the requested test and the Body current state and the Physical examination ONLY.
                '''

def return_body_test_results_user_prompt(self, tests_requested="", current_treatments="", translate=False):
    user_prompt = f'''
            Patient Profile: {self.medical_records['一般资料']}
            Body and pyschological profile: {self.profile}
            Current complaint: {self.medical_records['主诉']}
            Ground truth diagnosis: {self.medical_records['诊断结果']}
            Medical History (current and past): Current - {self.medical_records['现病史']} Past - {self.medical_records['既往史']}
            Current Treatments: {current_treatments}
            Test requested: {tests_requested}
            Body current state: {self.medical_records['辅助检查']}
            Physical examination: {self.medical_records['查体']}
            '''
    return user_prompt  

def check_body_test_results(self, test_requested="", test_response=""):
    system_prompt = f'''
                You are a sophisticated language model tasked with simulating the health state of a patient's body undergoing medical tests. You are tasked with analyzing the medical test results provided against the test requested, the body’s current state, and the physical examination provided below. 

                You MUST faithfully follow the data in the given information below. If you are satisfied that the test results given below are accurate with respect to the provided body’s current state and physical examination, then output the test results as they are without modification. If after your review, you are convinced that the results are incorrect, incomplete, or not related to the tests requested, then modify the test results and output these revised test results.

                #### Data Provided:
                - **Test results:** {test_response}
                - **Test requested:** {test_requested}
                - **Body's current state:** {self.medical_records['辅助检查']}
                - **Physical examination:** {self.medical_records['查体']}

                Output Format:
                - **Test requested 1:** <Results of test 1>
                - **Test requested 2:** <Results of test 2>
                - And so on.
                '''
    user_prompt = f'''

                You are to analyze the following data related to a patient's medical tests:

                #### Data Provided:
                - **Test results:** {test_response}
                - **Test requested:** {test_requested}
                - **Body's current state:** {self.medical_records['辅助检查']}
                - **Physical examination:** {self.medical_records['查体']}

                1. **Describe and analyze the given data:**
                - Identify the medical tests requested.
                - Evaluate the test results provided in the context of the body's current state and physical examination.

                2. **Theorize potential reasons for variations in outcomes:**
                - Consider why the test results might not align with the expected outcomes based on the body's current state and physical examination.
                - Discuss any inconsistencies or anomalies in the test results.

                3. **Suggest modifications to methodologies that could lead to improved outcomes:**
                - Propose changes to the testing process or methodology that might enhance the accuracy or relevance of future test results.

                ### Instructions for Analysis:
                - Use affirmative language and avoid negative directives.
                - Break down the task into manageable steps for clarity.

                ### Output Primer:
                Start your response with: "The analysis of the provided medical data indicates that..."

                ---

                ### Example:
                Given the following data:
                - **Test results:** Hemoglobin: 12 g/dL, WBC: 7000 cells/mcL
                - **Test requested:** Complete Blood Count (CBC)
                - **Body's current state:** Moderate anemia, slight fatigue
                - **Physical examination:** Pale skin, normal heart rate

                **Output: Assuming no modifications to the test results are necessary after your extensive review and anaylsis above.**
                ##Test results:## Hemoglobin: 12 g/dL, WBC: 7000 cells/mcL

                ---

                Use the provided structure and instructions to complete your analysis of the given medical data.

                '''
    user_prompt_original = f'''
                    You are a sophisticated language model tasked with simulating the health state of a patient's body undergoing medical tests. 
                    You are tasked with analysing the medical test results provided against the test requested and the Body current state and Physical examination provided below.
                    You MUST faithfull follow the data in the given information below.
                    If you are satisfied that the test results given below are accurate with respoect to the provided Body current state and Physical examination, then output the test results as they are without modification.
                    If after your review, you are convinced that the results are incorrect, incomplete or not related to the tests requested, then modify the test results and output these test results.

                    Test results: {test_response}    
                    Test requested: {test_requested}
                    Body current state: {self.medical_records['辅助检查']}
                    Physical examination: {self.medical_records['查体']}

                    <Test requested 1>: <Results of test 1>
                    <Test requested 2>: <Results or test 2>
                    and so on.
                '''
    
    return system_prompt, user_prompt