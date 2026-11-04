import sys
sys.path.insert(0, 'C:\\_Code\\conflu.ai')
from backend.app.domain.workflow.gate import evaluate_risk_reward, build_gate_input
inp = build_gate_input(entry_low=100.0, stop_loss=98.0, targets=[104.0, 110.0], risk_reward=2.0)
step = evaluate_risk_reward(inp)
print(f'Result: passed={step.passed}, conditional={step.conditional}, note="{step.note}"')