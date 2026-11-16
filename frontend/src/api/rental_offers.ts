import axios from './client';

export type RentalOfferStatus = 'pending' | 'countered' | 'accepted' | 'rejected' | 'withdrawn' | 'expired';

export type RentalOffer = {
  id: string;
  listing_id: string;
  tenant_id: string;
  landlord_id: string;
  proposed_rent: number;
  counter_rent?: number;
  status: RentalOfferStatus;
  move_in_date: string;
  message?: string;
  landlord_response?: string;
  tenant_response?: string;
  expires_at: string;
  responded_at?: string;
  created_at: string;
  updated_at?: string;
  property_address?: string;
  listing_title?: string;
  landlord_name?: string;
  tenant_name?: string;
};

export type RentalOfferCreate = {
  listing_id: string;
  proposed_rent: number;
  move_in_date: string;
  message?: string;
};

export type RentalOfferAction = {
  action: 'accept' | 'reject' | 'counter' | 'withdraw';
  response_message?: string;
  counter_rent?: number;
};

export const createRentalOffer = async (payload: RentalOfferCreate) => {
  const response = await axios.post('/api/rental_offers', payload);
  return response.data as RentalOffer;
};

export const getMyRentalOffers = async () => {
  const response = await axios.get<RentalOffer[]>('/api/rental_offers/mine');
  return response.data;
};

export const getLandlordRentalOffers = async () => {
  const response = await axios.get<RentalOffer[]>('/api/rental_offers/landlord');
  return response.data;
};

export const respondToRentalOffer = async (offerId: string, payload: RentalOfferAction) => {
  const response = await axios.post<RentalOffer>(`/api/rental_offers/${offerId}/respond`, payload);
  return response.data;
};

export const tenantRespondToRentalOffer = async (offerId: string, payload: RentalOfferAction) => {
  const response = await axios.post<RentalOffer>(`/api/rental_offers/${offerId}/tenant-respond`, payload);
  return response.data;
};