# Investment Management System

The investment management system allows insurance companies to invest their excess capital through a characteristic-based portfolio interface. The key innovation is that CFO skill affects perception, not returns.

## Core Concepts

### Portfolio Characteristics (5 Sliders)

1. **Risk** (0-100): Conservative to aggressive
2. **Duration** (0-100): Short-term to long-term investments  
3. **Liquidity** (0-100): How quickly assets can be converted to cash
4. **Credit** (0-100): AAA-only to high-yield acceptance
5. **Diversification** (0-100): Concentrated to highly diversified

### CFO Skill Effects

The CFO's skill level affects what they PERCEIVE, not actual returns:
- **Novice (skill <30)**: Up to 30% perception error, poor liquidation choices
- **Competent (skill 30-50)**: 15-20% perception error, mediocre decisions
- **Skilled (skill 50-70)**: 10-15% perception error, good decisions
- **Expert (skill 70-85)**: 5-10% perception error, excellent decisions
- **Master (skill 85+)**: 2-5% perception error, optimal decisions

### Example Scenarios

**Scenario 1: Novice CFO Disaster**
- Company sets aggressive portfolio (risk=80)
- Novice CFO perceives it as moderate (risk=50) due to 30% error
- Catastrophe hits, needs liquidation
- CFO sells liquid treasuries first (worst choice), keeping illiquid assets
- Result: 15% liquidation loss instead of 2%

**Scenario 2: Expert CFO Success**
- Same aggressive portfolio and catastrophe
- Expert correctly perceives high risk
- Liquidates illiquid assets first at better prices
- Result: Only 3% liquidation loss

## API Endpoints

- `POST /api/v1/investments/preferences` - Set portfolio characteristics
- `GET /api/v1/investments/portfolio` - View current portfolio (actual vs perceived)
- `GET /api/v1/investments/insights` - Get CFO analysis (quality varies by skill)
- `GET /api/v1/investments/liquidations` - View liquidation history
- `GET /api/v1/investments/constraints` - Get investment constraints

## Integration Points

- **Turn Processing**: Calculates returns each Monday
- **Employee System**: Uses CFO skill for perception effects
- **Capital Management**: Enforces minimum capital requirements
- **Crisis Events**: Triggers forced liquidations

## Configuration

Key parameters in game config:
```python
investment_parameters:
  min_investment_amount: 1000000  # $1M minimum
  max_investment_percentage: 0.8   # Max 80% of capital
  cfo_skill_effects:
    base_noise_level: 0.3         # 30% max perception error
    noise_reduction_rate: 0.9     # How skill reduces noise
```

## Future Enhancements

- Market condition effects on perception difficulty
- Learning from experience (skill improvement)
- More sophisticated liquidation strategies
- Integration with reinsurance for hedging 