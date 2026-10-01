import React from 'react';
import { Link } from 'react-router-dom';
import { Investigation } from '../../types';

interface InvestigationListProps {
  investigations: Investigation[];
  loading: boolean;
}

const InvestigationList: React.FC<InvestigationListProps> = ({ investigations, loading }) => {
  if (loading) {
    return <div className="p-4">Loading investigations...</div>;
  }

  if (investigations.length === 0) {
    return <div className="p-4 text-gray-500">No investigations found.</div>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full bg-white shadow-md rounded-lg overflow-hidden">
        <thead className="bg-gray-100">
          <tr>
            <th className="py-3 px-6 text-left font-semibold text-gray-700">Title</th>
            <th className="py-3 px-6 text-left font-semibold text-gray-700">Status</th>
            <th className="py-3 px-6 text-left font-semibold text-gray-700">Outcome</th>
            <th className="py-3 px-6 text-left font-semibold text-gray-700">Created At</th>
            <th className="py-3 px-6 text-center font-semibold text-gray-700">Action</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200">
          {investigations.map((inv) => (
            <tr key={inv.investigation_id} className="hover:bg-gray-50 transition-colors">
              <td className="py-4 px-6 text-gray-800 font-medium">{inv.title}</td>
              <td className="py-4 px-6">
                <span className={`px-3 py-1 rounded-full text-xs font-semibold
                  ${inv.status === 'OPEN' ? 'bg-green-100 text-green-800' : ''}
                  ${inv.status === 'UNDER_REVIEW' ? 'bg-yellow-100 text-yellow-800' : ''}
                  ${inv.status === 'CLOSED' ? 'bg-gray-100 text-gray-800' : ''}
                `}>
                  {inv.status}
                </span>
              </td>
              <td className="py-4 px-6 text-gray-600">
                {inv.outcome ? (
                  <span className={`px-2 py-1 rounded text-xs
                    ${inv.outcome === 'TRUE_POSITIVE' ? 'bg-red-100 text-red-800' : ''}
                    ${inv.outcome === 'FALSE_POSITIVE' ? 'bg-blue-100 text-blue-800' : ''}
                    ${inv.outcome === 'INCONCLUSIVE' ? 'bg-gray-100 text-gray-800' : ''}
                    ${inv.outcome === 'ESCALATED' ? 'bg-orange-100 text-orange-800' : ''}
                  `}>
                    {inv.outcome}
                  </span>
                ) : (
                  '-'
                )}
              </td>
              <td className="py-4 px-6 text-gray-500 text-sm">
                {new Date(inv.created_at).toLocaleDateString()}
              </td>
              <td className="py-4 px-6 text-center">
                <Link
                  to={`/investigations/${inv.investigation_id}`}
                  className="text-blue-600 hover:text-blue-800 font-medium text-sm"
                >
                  View Workspace
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default InvestigationList;
