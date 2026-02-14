import {
  OfferAccepted as OfferAcceptedEvent,
  OfferCreated as OfferCreatedEvent,
  OfferDeleted as OfferDeletedEvent,
  OfferUpdated as OfferUpdatedEvent,
} from "../generated/RealtYamProxy/RealtYamProxy"
import {
  OfferAccepted,
  OfferCreated,
  OfferDeleted,
  OfferUpdated,
} from "../generated/schema"
import { ethereum } from "@graphprotocol/graph-ts"

// Create a unique ID per log (tx hash + logIndex)
function getLogId(event: ethereum.Event): string {
  return event.transaction.hash.toHex() + "-" + event.logIndex.toString()
}

export function handleOfferCreated(event: OfferCreatedEvent): void {
  let entity = new OfferCreated(getLogId(event))

  entity.offerToken = event.params.offerToken
  entity.buyerToken = event.params.buyerToken
  entity.seller = event.params.seller
  entity.buyer = event.params.buyer
  entity.offerId = event.params.offerId
  entity.price = event.params.price
  entity.amount = event.params.amount

  entity.transactionHash = event.transaction.hash
  entity.logIndex = event.logIndex
  entity.blockNumber = event.block.number
  entity.timestamp = event.block.timestamp

  entity.save()
}

export function handleOfferAccepted(event: OfferAcceptedEvent): void {
  let entity = new OfferAccepted(getLogId(event))

  entity.offerId = event.params.offerId
  entity.seller = event.params.seller
  entity.buyer = event.params.buyer
  entity.offerToken = event.params.offerToken
  entity.buyerToken = event.params.buyerToken
  entity.price = event.params.price
  entity.amount = event.params.amount

  entity.transactionHash = event.transaction.hash
  entity.logIndex = event.logIndex
  entity.blockNumber = event.block.number
  entity.timestamp = event.block.timestamp

  entity.save()
}

export function handleOfferDeleted(event: OfferDeletedEvent): void {
  let entity = new OfferDeleted(getLogId(event))

  entity.offerId = event.params.offerId

  entity.transactionHash = event.transaction.hash
  entity.logIndex = event.logIndex
  entity.blockNumber = event.block.number
  entity.timestamp = event.block.timestamp

  entity.save()
}

export function handleOfferUpdated(event: OfferUpdatedEvent): void {
  let entity = new OfferUpdated(getLogId(event))

  entity.offerId = event.params.offerId
  entity.oldPrice = event.params.oldPrice
  entity.newPrice = event.params.newPrice
  entity.oldAmount = event.params.oldAmount
  entity.newAmount = event.params.newAmount

  entity.transactionHash = event.transaction.hash
  entity.logIndex = event.logIndex
  entity.blockNumber = event.block.number
  entity.timestamp = event.block.timestamp

  entity.save()
}
