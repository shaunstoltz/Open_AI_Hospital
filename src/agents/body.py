from .base_agent import Agent
from utils.register import register_class, registry

@register_class(alias="Agent.PatientBody.GPT")
class PatientBody(Agent):
    def __init__(self, args):

        engine = registry.get_class("Engine.LiteLLM")(
            openai_api_key=args.patient_openai_api_key, 
            openai_api_base=args.patient_openai_api_base,
            openai_model_name=args.patient_openai_model_name, 
            temperature=args.patient_temperature, 
            max_tokens=args.patient_max_tokens,
            top_p=args.patient_top_p,
            frequency_penalty=args.patient_frequency_penalty,
            presence_penalty=args.patient_presence_penalty
        )

        self.system_message = ""
        if args.approach == "base" or args.approach == "p26":
            from agents.prompt_templates.principles.body_prompts import system_prompt, return_body_test_results_user_prompt

            self.system_message = system_prompt
            self.return_body_test_results_user_prompt = return_body_test_results_user_prompt        

        super(PatientBody, self).__init__(engine)



    def speak_test_results(self, role="test_results", save_to_memory=True, test_requested="", current_treatments="", translate=False):


        messages = [{"role": "system", "content": self.system_message}]
        content = self.return_body_test_results_user_prompt(self, tests_requested=test_requested, current_treatments=current_treatments, translate=translate)
        messages.append({"role": "user", "content": f"<{content}"})

        response = self.engine.get_response(messages)
        
        if save_to_memory:
            self.memorize(("user", f"<{role}> {content}"))
            self.memorize(("assistant", response))

        return response
    
    def speak_check_results(self, patient, test_requested="", test_results=""):
        from agents.prompt_templates.principles.body_prompts import check_body_test_results

        user_prompt, system_prompt = check_body_test_results(patient, test_requested, test_results)

        messages = [{"role": "system", "content": system_prompt}]
        messages.append({"role": "user", "content": f"<{user_prompt}"})

        response = self.engine.get_response(messages)
        
        self.memorize(("user", f"<test checker> {user_prompt}"))
        self.memorize(("assistant", response))

        return response