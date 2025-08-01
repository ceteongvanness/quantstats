#!/usr/bin/env python3
"""
Test script to demonstrate the drawdown calculation bug and verify the fix.
"""

import pandas as pd
import numpy as np
import quantstats as qs
from datetime import datetime, timedelta


def create_test_data():
    """Create test data with specific drawdown patterns."""
    
    # Create date range for 6 months of daily data
    dates = pd.date_range(start='2023-01-01', end='2023-06-30', freq='D')
    
    # Test Case 1: First month has drawdown (starts with negative return)
    # This should trigger the bug in the current implementation
    returns_case1 = []
    for i, date in enumerate(dates):
        if i == 0:
            # First return is negative (drawdown)
            returns_case1.append(-0.05)  # -5% on first day
        elif i <= 20:  # Rest of first month
            returns_case1.append(np.random.normal(0.001, 0.02))  # Small positive drift
        elif i <= 40:  # Second month - recovery
            returns_case1.append(np.random.normal(0.002, 0.015))  # Stronger recovery
        else:  # Rest of period
            returns_case1.append(np.random.normal(0.0005, 0.02))  # Normal returns
    
    # Test Case 2: No drawdown in first month (starts with positive return)
    # This should work correctly with current implementation
    returns_case2 = []
    for i, date in enumerate(dates):
        if i == 0:
            # First return is positive
            returns_case2.append(0.02)  # +2% on first day
        elif i <= 20:  # First month
            returns_case2.append(np.random.normal(0.001, 0.015))  # Positive drift
        elif i <= 40:  # Second month - drawdown period
            returns_case2.append(np.random.normal(-0.001, 0.025))  # Negative drift
        else:  # Rest of period
            returns_case2.append(np.random.normal(0.0005, 0.02))  # Normal returns
    
    # Create pandas Series
    case1_series = pd.Series(returns_case1, index=dates, name='First_Month_Drawdown')
    case2_series = pd.Series(returns_case2, index=dates, name='No_First_Month_Drawdown')
    
    return case1_series, case2_series


def test_current_implementation():
    """Test the current implementation to demonstrate the bug."""
    print("=" * 60)
    print("TESTING CURRENT IMPLEMENTATION (WITH BUG)")
    print("=" * 60)
    
    case1, case2 = create_test_data()
    
    print(f"Test Case 1 - First return: {case1.iloc[0]:.4f} (negative)")
    print(f"Test Case 2 - First return: {case2.iloc[0]:.4f} (positive)")
    print()
    
    # Test max_drawdown
    case1_max_dd = qs.stats.max_drawdown(case1)
    case2_max_dd = qs.stats.max_drawdown(case2)
    
    print(f"Case 1 Max Drawdown: {case1_max_dd:.4f}")
    print(f"Case 2 Max Drawdown: {case2_max_dd:.4f}")
    print()
    
    # Test to_drawdown_series
    case1_dd_series = qs.stats.to_drawdown_series(case1)
    case2_dd_series = qs.stats.to_drawdown_series(case2)
    
    print(f"Case 1 First 5 drawdown values:")
    print(case1_dd_series.head())
    print(f"Case 1 Minimum drawdown in series: {case1_dd_series.min():.4f}")
    print()
    
    print(f"Case 2 First 5 drawdown values:")
    print(case2_dd_series.head())
    print(f"Case 2 Minimum drawdown in series: {case2_dd_series.min():.4f}")
    print()
    
    # The bug: Case 1 should show a larger drawdown than what's calculated
    # because the first negative return creates an immediate drawdown that's not properly captured
    
    return {
        'case1': {'max_dd': case1_max_dd, 'dd_series': case1_dd_series},
        'case2': {'max_dd': case2_max_dd, 'dd_series': case2_dd_series}
    }


def fixed_max_drawdown(prices):
    """Fixed implementation of max_drawdown function."""
    # Validate input (assuming validate_input exists)
    if hasattr(qs.stats, 'validate_input'):
        qs.stats.validate_input(prices)
    
    # Prepare prices (convert from returns if needed)
    prices = qs.utils._prepare_prices(prices)
    
    if len(prices) == 0:
        return 0.0
    
    # Add phantom baseline point to handle edge case
    try:
        time_delta = prices.index.freq or pd.Timedelta(days=1)
    except:
        time_delta = pd.Timedelta(days=1)
    
    phantom_date = prices.index[0] - time_delta
    
    # Use the base value from to_prices function (1e5) as baseline
    baseline_value = 1e5
    
    # Create extended series with phantom baseline
    extended_prices = prices.copy()
    extended_prices.loc[phantom_date] = baseline_value
    extended_prices = extended_prices.sort_index()
    
    # Calculate drawdown
    return (extended_prices / extended_prices.expanding(min_periods=0).max()).min() - 1


def fixed_to_drawdown_series(returns):
    """Fixed implementation of to_drawdown_series function."""
    # Validate input (assuming validate_input exists)
    if hasattr(qs.stats, 'validate_input'):
        qs.stats.validate_input(returns)
    
    # Convert returns to prices
    prices = qs.utils._prepare_prices(returns)
    
    if len(prices) == 0:
        return pd.Series([], dtype=float, index=returns.index)
    
    # Add phantom baseline point
    try:
        time_delta = prices.index.freq or pd.Timedelta(days=1)
    except:
        time_delta = pd.Timedelta(days=1)
    
    phantom_date = prices.index[0] - time_delta
    
    # Use the base value from to_prices function (1e5) as baseline
    baseline_value = 1e5
    
    # Create extended series with phantom baseline
    extended_prices = prices.copy()
    extended_prices.loc[phantom_date] = baseline_value
    extended_prices = extended_prices.sort_index()
    
    # Calculate drawdown series
    dd = extended_prices / np.maximum.accumulate(extended_prices) - 1.0
    
    # Remove phantom point and return original time series
    dd = dd.drop(phantom_date)
    
    # Clean up infinite and zero values
    return dd.replace([np.inf, -np.inf, -0], 0)


def test_fixed_implementation():
    """Test the fixed implementation."""
    print("=" * 60)
    print("TESTING FIXED IMPLEMENTATION")
    print("=" * 60)
    
    case1, case2 = create_test_data()
    
    print(f"Test Case 1 - First return: {case1.iloc[0]:.4f} (negative)")
    print(f"Test Case 2 - First return: {case2.iloc[0]:.4f} (positive)")
    print()
    
    # Test fixed max_drawdown
    case1_max_dd = fixed_max_drawdown(case1)
    case2_max_dd = fixed_max_drawdown(case2)
    
    print(f"Case 1 Max Drawdown (FIXED): {case1_max_dd:.4f}")
    print(f"Case 2 Max Drawdown (FIXED): {case2_max_dd:.4f}")
    print()
    
    # Test fixed to_drawdown_series
    case1_dd_series = fixed_to_drawdown_series(case1)
    case2_dd_series = fixed_to_drawdown_series(case2)
    
    print(f"Case 1 First 5 drawdown values (FIXED):")
    print(case1_dd_series.head())
    print(f"Case 1 Minimum drawdown in series (FIXED): {case1_dd_series.min():.4f}")
    print()
    
    print(f"Case 2 First 5 drawdown values (FIXED):")
    print(case2_dd_series.head())
    print(f"Case 2 Minimum drawdown in series (FIXED): {case2_dd_series.min():.4f}")
    print()
    
    return {
        'case1': {'max_dd': case1_max_dd, 'dd_series': case1_dd_series},
        'case2': {'max_dd': case2_max_dd, 'dd_series': case2_dd_series}
    }


def compare_results(original_results, fixed_results):
    """Compare results between original and fixed implementations."""
    print("=" * 60)
    print("COMPARISON OF RESULTS")
    print("=" * 60)
    
    print("MAX DRAWDOWN COMPARISON:")
    print(f"Case 1 (First month drawdown):")
    print(f"  Original: {original_results['case1']['max_dd']:.6f}")
    print(f"  Fixed:    {fixed_results['case1']['max_dd']:.6f}")
    print(f"  Difference: {abs(fixed_results['case1']['max_dd'] - original_results['case1']['max_dd']):.6f}")
    print()
    
    print(f"Case 2 (No first month drawdown):")
    print(f"  Original: {original_results['case2']['max_dd']:.6f}")
    print(f"  Fixed:    {fixed_results['case2']['max_dd']:.6f}")
    print(f"  Difference: {abs(fixed_results['case2']['max_dd'] - original_results['case2']['max_dd']):.6f}")
    print()
    
    print("DRAWDOWN SERIES COMPARISON:")
    print(f"Case 1 - First drawdown value (should be ~-5%):")
    print(f"  Original: {original_results['case1']['dd_series'].iloc[0]:.6f}")
    print(f"  Fixed:    {fixed_results['case1']['dd_series'].iloc[0]:.6f}")
    print()
    
    print(f"Case 2 - First drawdown value (should be ~0%):")
    print(f"  Original: {original_results['case2']['dd_series'].iloc[0]:.6f}")
    print(f"  Fixed:    {fixed_results['case2']['dd_series'].iloc[0]:.6f}")
    print()
    
    # Expected behavior analysis
    print("EXPECTED BEHAVIOR ANALYSIS:")
    print("- Case 1 should show the first day as a ~5% drawdown")
    print("- Case 2 should show the first day as ~0% drawdown")
    print("- The fixed implementation should correctly capture the immediate drawdown in Case 1")
    print("- Both implementations should be similar for Case 2")


def detailed_analysis():
    """Provide detailed analysis of the issue."""
    print("=" * 60)
    print("DETAILED ANALYSIS")
    print("=" * 60)
    
    # Create a simple example to illustrate the issue
    simple_returns = pd.Series([-0.05, 0.02, 0.01, -0.01, 0.03], 
                              index=pd.date_range('2023-01-01', periods=5, freq='D'))
    
    print("Simple example with -5% first return:")
    print(simple_returns)
    print()
    
    # Show what happens during conversion to prices
    prices = qs.utils._prepare_prices(simple_returns)
    print("Converted to prices:")
    print(prices)
    print()
    
    # Show original drawdown calculation
    original_dd = qs.stats.to_drawdown_series(simple_returns)
    print("Original drawdown series:")
    print(original_dd)
    print()
    
    # Show fixed drawdown calculation
    fixed_dd = fixed_to_drawdown_series(simple_returns)
    print("Fixed drawdown series:")
    print(fixed_dd)
    print()
    
    print("The key difference:")
    print(f"- Original first drawdown: {original_dd.iloc[0]:.6f}")
    print(f"- Fixed first drawdown: {fixed_dd.iloc[0]:.6f}")
    print(f"- Expected first drawdown: ~-0.05 (the actual first return)")


if __name__ == "__main__":
    print("Drawdown Calculation Bug Test")
    print("=============================")
    print()
    
    # Set random seed for reproducible results
    np.random.seed(42)
    
    # Test current implementation
    original_results = test_current_implementation()
    
    # Test fixed implementation
    fixed_results = test_fixed_implementation()
    
    # Compare results
    compare_results(original_results, fixed_results)
    
    # Detailed analysis
    detailed_analysis()
    
    print("\n" + "=" * 60)
    print("CONCLUSION")
    print("=" * 60)
    print("The bug is demonstrated by the difference in drawdown calculations")
    print("when the first return is negative. The fixed implementation properly")
    print("captures the immediate drawdown, while the original implementation")
    print("underestimates it due to the missing baseline reference point.")