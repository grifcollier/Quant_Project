import { NextResponse } from 'next/server';
import { getOrders } from '@/lib/alpaca';

export async function GET() {
  try {
    return NextResponse.json(await getOrders());
  } catch (e: unknown) {
    return NextResponse.json({ error: (e as Error).message }, { status: 502 });
  }
}
