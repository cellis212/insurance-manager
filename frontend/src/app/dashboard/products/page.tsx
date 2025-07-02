'use client';

import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { queryClient } from '@/lib/query-client';
import { CubeIcon, ArrowsUpDownIcon, PlusIcon } from '@heroicons/react/24/outline';

interface State {
  id: string;
  code: string;
  name: string;
}

interface LineOfBusiness {
  id: string;
  code: string;
  name: string;
}

interface Product {
  id: string;
  company_id: string;
  state_code: string;
  line_of_business_code: string;
  tier: string;
  base_premium: number;
  deductible: number;
  coverage_limit: number;
  active_policies: number;
  market_share: number;
  effective_loss_ratio: number;
  has_pending_switch: boolean;
  pending_tier?: string;
  switch_effective_date?: string;
}

interface TierInfo {
  tier: string;
  price_modifier: number;
  risk_selection: number;
  demand_elasticity: number;
  retention_rate: number;
  expense_ratio: number;
  description: {
    pricing: string;
    target_market: string;
    risk_profile: string;
  };
}

interface CompanyInfo {
  authorized_states: Array<{ state: State }>;
}

export default function ProductsPage() {
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [showAddProduct, setShowAddProduct] = useState(false);
  const [newProductState, setNewProductState] = useState('');
  const [newProductLine, setNewProductLine] = useState('');
  const [newProductTier, setNewProductTier] = useState('Standard');
  const [newProductPremium, setNewProductPremium] = useState('1000');

  const { data: products, isLoading } = useQuery({
    queryKey: ['products'],
    queryFn: () => apiClient.get<Product[]>('/products'),
  });

  const { data: tierInfo } = useQuery({
    queryKey: ['tier-info'],
    queryFn: () => apiClient.get<TierInfo[]>('/products/tiers'),
  });

  const { data: companyInfo } = useQuery({
    queryKey: ['company-info'],
    queryFn: () => apiClient.get<CompanyInfo>('/game/company'),
  });

  const { data: linesOfBusiness } = useQuery({
    queryKey: ['lines-of-business'],
    queryFn: () => apiClient.get<LineOfBusiness[]>('/game/lines-of-business'),
  });

  const switchTierMutation = useMutation({
    mutationFn: ({ productId, newTier }: { productId: string; newTier: string }) => 
      apiClient.post(`/products/${productId}/switch-tier`, { new_tier: newTier }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
      setSelectedProduct(null);
    },
  });

  const createProductMutation = useMutation({
    mutationFn: (data: {
      state_id: string;
      line_of_business_id: string;
      tier: string;
      base_premium: number;
      deductible: number;
      coverage_limit: number;
    }) => apiClient.post('/products', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
      setShowAddProduct(false);
      setNewProductState('');
      setNewProductLine('');
      setNewProductTier('Standard');
      setNewProductPremium('1000');
    },
  });

  const formatCurrency = (amount: number) => 
    new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);

  const formatPercent = (value: number) => 
    new Intl.NumberFormat('en-US', {
      style: 'percent',
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    }).format(value);

  const getTierColor = (tier: string) => {
    switch (tier) {
      case 'Premium': return 'text-purple-600 bg-purple-50';
      case 'Standard': return 'text-blue-600 bg-blue-50';
      case 'Basic': return 'text-gray-600 bg-gray-50';
      default: return 'text-gray-600 bg-gray-50';
    }
  };

  const getLossRatioColor = (ratio: number) => {
    if (ratio < 0.6) return 'text-green-600';
    if (ratio < 0.7) return 'text-gray-600';
    if (ratio < 0.8) return 'text-yellow-600';
    return 'text-red-600';
  };

  if (isLoading) {
    return (
      <div className="p-8">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded w-1/4 mb-8"></div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="bg-white p-6 rounded-lg shadow">
                <div className="h-6 bg-gray-200 rounded w-3/4 mb-2"></div>
                <div className="h-4 bg-gray-200 rounded w-1/2"></div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="mb-8 flex justify-between items-start">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Product Management</h1>
          <p className="mt-1 text-sm text-gray-600">
            Manage your insurance products across states and lines of business
          </p>
        </div>
        <button
          onClick={() => setShowAddProduct(true)}
          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700"
        >
          <PlusIcon className="h-5 w-5 mr-2" />
          Add Product
        </button>
      </div>

      {/* Products Grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {products?.map((product) => (
          <div key={product.id} className="bg-white p-6 rounded-lg shadow">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h3 className="text-lg font-medium text-gray-900">
                  {product.state_code} - {product.line_of_business_code}
                </h3>
                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getTierColor(product.tier)}`}>
                  {product.tier} Tier
                </span>
              </div>
              <CubeIcon className="h-6 w-6 text-gray-400" />
            </div>

            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Base Premium:</span>
                <span className="font-medium">{formatCurrency(product.base_premium)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Active Policies:</span>
                <span className="font-medium">{product.active_policies.toLocaleString()}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Market Share:</span>
                <span className="font-medium">{formatPercent(product.market_share)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Loss Ratio:</span>
                <span className={`font-medium ${getLossRatioColor(product.effective_loss_ratio)}`}>
                  {formatPercent(product.effective_loss_ratio)}
                </span>
              </div>
            </div>

            {product.has_pending_switch && (
              <div className="mt-3 bg-yellow-50 rounded-md p-2">
                <p className="text-xs text-yellow-800">
                  Switching to {product.pending_tier} tier on {product.switch_effective_date}
                </p>
              </div>
            )}

            {!product.has_pending_switch && (
              <button
                onClick={() => setSelectedProduct(product)}
                className="mt-4 w-full inline-flex items-center justify-center px-3 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
              >
                <ArrowsUpDownIcon className="h-4 w-4 mr-2" />
                Switch Tier
              </button>
            )}
          </div>
        ))}
      </div>

      {/* Switch Tier Modal */}
      {selectedProduct && (
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-lg w-full p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">
              Switch Product Tier
            </h3>
            
            <div className="mb-6">
              <p className="text-sm text-gray-600 mb-2">
                Current tier: <span className="font-medium">{selectedProduct.tier}</span>
              </p>
              <p className="text-sm text-gray-600">
                Product: {selectedProduct.state_code} - {selectedProduct.line_of_business_code}
              </p>
            </div>

            <div className="space-y-3 mb-6">
              {tierInfo?.filter(t => t.tier !== selectedProduct.tier).map((tier) => (
                <label key={tier.tier} className="relative block cursor-pointer rounded-lg border bg-white px-6 py-4 shadow-sm focus:outline-none sm:flex sm:justify-between">
                  <input
                    type="radio"
                    name="tier"
                    value={tier.tier}
                    className="sr-only"
                    onChange={(e) => {
                      if (e.target.checked) {
                        // Will use this value when submitting
                      }
                    }}
                  />
                  <span className="flex items-center">
                    <span className="flex flex-col text-sm">
                      <span className="font-medium text-gray-900">{tier.tier} Tier</span>
                      <span className="text-gray-500">
                        {tier.description.pricing} • {tier.description.target_market}
                      </span>
                    </span>
                  </span>
                  <span className="mt-2 flex text-sm sm:mt-0 sm:ml-4 sm:flex-col sm:text-right">
                    <span className="font-medium text-gray-900">
                      {tier.price_modifier > 1 ? '+' : ''}{formatPercent(tier.price_modifier - 1)} price
                    </span>
                    <span className="text-gray-500">
                      {tier.risk_selection > 1 ? '+' : ''}{formatPercent(tier.risk_selection - 1)} risk
                    </span>
                  </span>
                </label>
              ))}
            </div>

            <div className="bg-amber-50 rounded-md p-4 mb-6">
              <p className="text-sm text-amber-800">
                <strong>Cost:</strong> $50,000 • <strong>Time:</strong> 2 weeks to take effect
              </p>
              {selectedProduct.active_policies > 0 && (
                <p className="text-sm text-amber-800 mt-1">
                  Customer notification required for {selectedProduct.active_policies.toLocaleString()} active policies
                </p>
              )}
            </div>

            <div className="flex space-x-3">
              <button
                onClick={() => {
                  const selectedTier = (document.querySelector('input[name="tier"]:checked') as HTMLInputElement)?.value;
                  if (selectedTier) {
                    switchTierMutation.mutate({
                      productId: selectedProduct.id,
                      newTier: selectedTier,
                    });
                  }
                }}
                disabled={switchTierMutation.isPending}
                className="flex-1 px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {switchTierMutation.isPending ? 'Switching...' : 'Confirm Switch'}
              </button>
              <button
                onClick={() => setSelectedProduct(null)}
                className="flex-1 px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add Product Modal */}
      {showAddProduct && (
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-lg w-full p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">
              Add New Product
            </h3>

            <div className="space-y-4 mb-6">
              <div>
                <label className="block text-sm font-medium text-gray-700">State</label>
                <select
                  value={newProductState}
                  onChange={(e) => setNewProductState(e.target.value)}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                >
                  <option value="">Select a state</option>
                  {companyInfo?.authorized_states.map((auth) => (
                    <option key={auth.state.id} value={auth.state.id}>
                      {auth.state.name} ({auth.state.code})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">Line of Business</label>
                <select
                  value={newProductLine}
                  onChange={(e) => setNewProductLine(e.target.value)}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                >
                  <option value="">Select a line</option>
                  {linesOfBusiness?.map((line) => (
                    <option key={line.id} value={line.id}>
                      {line.name} ({line.code})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">Product Tier</label>
                <select
                  value={newProductTier}
                  onChange={(e) => setNewProductTier(e.target.value)}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                >
                  <option value="Basic">Basic</option>
                  <option value="Standard">Standard</option>
                  <option value="Premium">Premium</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">Base Annual Premium</label>
                <div className="mt-1 relative rounded-md shadow-sm">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <span className="text-gray-500 sm:text-sm">$</span>
                  </div>
                  <input
                    type="number"
                    value={newProductPremium}
                    onChange={(e) => setNewProductPremium(e.target.value)}
                    className="focus:ring-indigo-500 focus:border-indigo-500 block w-full pl-7 pr-12 sm:text-sm border-gray-300 rounded-md"
                    placeholder="1000"
                  />
                </div>
              </div>
            </div>

            <div className="flex space-x-3">
              <button
                onClick={() => {
                  if (newProductState && newProductLine && newProductPremium) {
                    createProductMutation.mutate({
                      state_id: newProductState,
                      line_of_business_id: newProductLine,
                      tier: newProductTier,
                      base_premium: parseFloat(newProductPremium),
                      deductible: newProductTier === 'Basic' ? 1000 : newProductTier === 'Premium' ? 250 : 500,
                      coverage_limit: newProductTier === 'Basic' ? 100000 : newProductTier === 'Premium' ? 1000000 : 300000,
                    });
                  }
                }}
                disabled={createProductMutation.isPending || !newProductState || !newProductLine || !newProductPremium}
                className="flex-1 px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {createProductMutation.isPending ? 'Creating...' : 'Create Product'}
              </button>
              <button
                onClick={() => {
                  setShowAddProduct(false);
                  setNewProductState('');
                  setNewProductLine('');
                  setNewProductTier('Standard');
                  setNewProductPremium('1000');
                }}
                className="flex-1 px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
} 