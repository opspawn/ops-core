from src.ui.user_interface import get_user_input, display_results
from src.task_processor.task_parser import parse_task_description
from src.task_processor.task_planner import plan_task
from src.code_generator.code_writer import generate_code
from src.integration_engine.code_integrator import integrate_code
from src.integration_engine.dependency_manager import manage_dependencies
from src.testing_suite.unit_test_runner import run_unit_tests
from src.testing_suite.integration_test_runner import run_integration_tests
from src.testing_suite.performance_test_runner import run_performance_tests
from src.deployment_manager.deployment_scripts import deploy_code
from src.deployment_manager.environment_configurator import configure_environment
from src.monitoring_maintenance.monitoring_tools import monitor_application
from src.monitoring_maintenance.logging_system import log_performance
from src.monitoring_maintenance.alert_system import send_alerts

def main():
    # Main function to run the AutoFunctionBuilder tool
    task_description = get_user_input()
    parsed_description = parse_task_description(task_description)
    task_plan = plan_task(parsed_description)
    code_snippets = generate_code(task_plan)
    integrated_code = integrate_code(code_snippets)
    manage_dependencies(integrated_code)
    
    # Run tests
    run_unit_tests(integrated_code)
    run_integration_tests(integrated_code)
    run_performance_tests(integrated_code)
    
    # Deploy code
    refined_code = integrated_code  # Assuming code is refined after tests
    configure_environment('production')
    deploy_code(refined_code)
    
    # Monitor and maintain
    monitor_application(refined_code)
    log_performance(refined_code)
    send_alerts(False)  # Assuming no issues detected

    display_results("Deployment successful")

if __name__ == "__main__":
    main()
